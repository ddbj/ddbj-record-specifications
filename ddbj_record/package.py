"""DDBJ Record v4 のパッケージ: record を 1 つの zip にしたもの。

record のうち 1 つしかないもの(submission、projects など)は record.json に、数に上限の無い
オブジェクトの list(samples、sequences.entries、features など)は list ごとの JSON Lines に、
配列は sequences/ の下の FASTA に置く。形は docs/v4-schema.md。ここにあるのは次のもの。

- read_record: record.json だけを読む。JSON Lines も配列も読まない
- iter_objects: JSON Lines の 1 つを、1 行ずつモデルにして返す
- load_record: record 全体(配列を除く)を組み立てる。小さい record 用
- check: パッケージが約束どおりかを確かめ、外れているものを挙げる。どのファイルも流して読む
- pack: v3 の record(1 つの JSON で、entry に配列を書いたもの)を、v4 のパッケージにする
- unpack: v4 のパッケージを、v3 の record に戻す。配列も読むので、小さい record 用

pack / unpack は v3 と v4 の間の converter だが、ddbj_record/converter/ の converter (JSON の record を
受け取り、JSON の record を返す) と違い、zip のパッケージを読み書きし、check と同じ約束を使うので、ここに置く。
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import lzma
import os
import re
import stat
import struct
import sys
import tempfile
import zipfile
import zlib
from collections import Counter
from collections.abc import Iterable, Iterator
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import IO, Any, Final, Literal, TypeVar, overload

from pydantic import BaseModel, ValidationError

from ddbj_record.schema import v3, v4

MIMETYPE = "application/vnd.ddbj.record+zip"
MIMETYPE_NAME: Final = "mimetype"
RECORD_NAME: Final = "record.json"
# major だけで、minor は付けない (docs/versioning.md)。
SCHEMA_VERSION = "v4"
V3_SCHEMA_VERSION = "v3"

# 数に上限の無いオブジェクトの list と、それを置く JSON Lines。list の場所は record の中のパス。
COLLECTIONS: dict[str, tuple[tuple[str, ...], type[BaseModel]]] = {
    "samples.jsonl": (("samples",), v3.Sample),
    "experiments.jsonl": (("experiments",), v3.Experiment),
    "runs.jsonl": (("runs",), v3.Run),
    "analyses.jsonl": (("analyses",), v3.Analysis),
    "datasets.jsonl": (("datasets",), v3.Dataset),
    "entries.jsonl": (("sequences", "entries"), v4.Entry),
    "features.jsonl": (("features",), v3.Feature),
    "relations.jsonl": (("relations",), v3.Relation),
}
ENTRIES_NAME: Final = "entries.jsonl"
RESERVED_NAMES = frozenset({MIMETYPE_NAME, RECORD_NAME, *COLLECTIONS})

# 配列を置く FASTA。sequences/ のすぐ下に幾つでも置いてよく、分け方は record に書かない。
# 名前は、どの OS のファイル名にもなる文字に限る(大文字小文字だけが違う名前も重ねない)。
FASTA_NAME = re.compile(r"sequences/[A-Za-z0-9_-][A-Za-z0-9_.-]*\.fa")
DEFAULT_FASTA: Final = "sequences/entries.fa"

# 配列を持つ entry の alias は FASTA の見出しになるので、空白の無い印字可能な ASCII に限る。
# メンバーの名前も同じ。ASCII に限れば、zip の名前の文字コードを取り違えることがない。
PRINTABLE_ASCII = re.compile(r"[!-~]+")
LETTERS = re.compile(r"[A-Za-z]*")
ASCII_WHITESPACE = re.compile(r"[ \t\r\n]+")

FASTA_WIDTH = 80
# FASTA を読む単位。1 行がどれだけ長くても、使うメモリはこれで決まる。
CHUNK_SIZE = 1 << 20
# 見出しと alias の長さの上限。
MAX_HEADER = 4096
# JSON Lines の 1 行と record.json の上限。配列は FASTA に、数の多いものは JSON Lines に出すので、
# 1 つのオブジェクトと record.json はこれに収まる。
MAX_LINE = 1 << 20
MAX_RECORD = 4 << 20
# 1 つのファイルについて挙げる問題の数。壊れたファイルが問題の一覧でメモリを使い切らないように。
MAX_PROBLEMS_PER_FILE = 100
# 問題の文に入れる、名前や場所の長さ。
MAX_QUOTE = 80

COMPRESSIONS = frozenset({zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED})

# zip のローカルファイルヘッダー (APPNOTE.TXT 4.3.7)。先頭のメンバーを、目次の順ではなくファイルの中の位置で確かめる。
LOCAL_HEADER = struct.Struct("<4sHHHHHIIIHH")
LOCAL_HEADER_SIGNATURE = b"PK\x03\x04"
ENCRYPTED_FLAG = 0x01
DATA_DESCRIPTOR_FLAG = 0x08

# 壊れた zip を読んだときに出うる例外。check はこれを問題として挙げ、例外にしない。
READ_ERRORS = (
    zipfile.BadZipFile,
    zlib.error,
    lzma.LZMAError,
    OSError,
    EOFError,
    ValueError,
    NotImplementedError,
    RuntimeError,
)


# I-JSON (RFC 7493 §2.2) の数の範囲。整数は IEEE 754 の倍精度で正しく表せるもの、小数は倍精度が区別できる
# 有効数字 17 桁まで。
MAX_SAFE_INTEGER = 2**53 - 1
MAX_SIGNIFICANT_DIGITS = 17

Model = TypeVar("Model", bound=BaseModel)


class PackageError(Exception):
    """パッケージとして読めない(zip でない、record.json が無い、約束に合わない)か、作れない。"""


def sequence_digest(chunks: Iterable[str]) -> str:
    """GA4GH refget の sha512t24u: 大文字にした配列の SHA-512 の先頭 24 バイトを base64url で。"""
    sha512 = hashlib.sha512()
    for chunk in chunks:
        sha512.update(chunk.upper().encode("ascii"))
    return _digest(sha512)


# --- 読む


def read_record(path: Path) -> v4.DdbjRecord:
    """パッケージの record.json だけを読む。JSON Lines にある list は空のまま。

    record.json が約束に合わなければ(v4 でない、JSON Lines に置く list を持つ) PackageError を上げる。
    """
    with _open(path) as package:
        record = _strict(RECORD_NAME, _read_record_json(package), v4.DdbjRecord)
    if problems := _record_problems(record):
        raise PackageError(problems[0])
    return record


@overload
def iter_objects(path: Path, name: Literal["samples.jsonl"]) -> Iterator[v3.Sample]: ...
@overload
def iter_objects(path: Path, name: Literal["experiments.jsonl"]) -> Iterator[v3.Experiment]: ...
@overload
def iter_objects(path: Path, name: Literal["runs.jsonl"]) -> Iterator[v3.Run]: ...
@overload
def iter_objects(path: Path, name: Literal["analyses.jsonl"]) -> Iterator[v3.Analysis]: ...
@overload
def iter_objects(path: Path, name: Literal["datasets.jsonl"]) -> Iterator[v3.Dataset]: ...
@overload
def iter_objects(path: Path, name: Literal["entries.jsonl"]) -> Iterator[v4.Entry]: ...
@overload
def iter_objects(path: Path, name: Literal["features.jsonl"]) -> Iterator[v3.Feature]: ...
@overload
def iter_objects(path: Path, name: Literal["relations.jsonl"]) -> Iterator[v3.Relation]: ...
@overload
def iter_objects(path: Path, name: str) -> Iterator[BaseModel]: ...


def iter_objects(path: Path, name: str) -> Iterator[BaseModel]:
    """JSON Lines の 1 つ(例えば samples.jsonl)を、1 行ずつモデルにして返す。無ければ何も返さない。

    約束に合わない行があれば PackageError を上げる。黙って飛ばすと、後の行の位置(relation の index)がずれる。
    """
    if name not in COLLECTIONS:
        raise PackageError(f"{name}: not a list of the record")
    _, model = COLLECTIONS[name]
    with _open(path) as package:
        if not _has(package, name):
            return
        problems = _Problems(name)
        lines = 0
        try:
            with package.open(name) as member:
                for number, line in _lines(member, problems):
                    if problems.items:
                        break
                    lines += 1
                    yield _strict(f"{name}:{number}", line, model)
        except READ_ERRORS as e:
            raise PackageError(f"{path}: {name} cannot be read: {e}") from e
        if problems.items:
            raise PackageError(problems.items[0])
        if lines == 0:
            raise PackageError(f"{name}: empty; an empty list has no file")


def load_record(path: Path) -> v4.DdbjRecord:
    """record 全体(配列を除く)を組み立てる。JSON Lines を全て読むので、大きい record には使わない。"""
    record = read_record(path).model_dump(exclude_none=True)
    for name, (location, _) in COLLECTIONS.items():
        objects = [obj.model_dump(exclude_none=True) for obj in iter_objects(path, name)]
        if objects:
            _place(record, location, objects)
    return v4.DdbjRecord.model_validate(record)


def unpack(path: Path) -> dict[str, Any]:
    """パッケージを、v3 の record(1 つの JSON で、entry に配列を書いたもの)に戻す。

    配列を全てメモリに読むので、小さい record と、v3 を読む側のための移し替えに使う。
    """
    if problems := check(path):
        raise PackageError("; ".join(problems[:10]))

    record = load_record(path).model_dump(exclude_none=True)
    sequences: dict[str, str] = {}
    with _open(path) as package:
        for name in sorted(n for n in package.namelist() if FASTA_NAME.fullmatch(n)):
            with package.open(name) as fasta:
                alias: str | None = None
                parts: list[str] = []
                for raw in fasta:
                    line = raw.rstrip(b"\r\n").decode("ascii")
                    if line.startswith(">"):
                        if alias is not None:
                            sequences[alias] = "".join(parts)
                        alias, parts = line[1:], []
                    elif line:
                        parts.append(line)
                if alias is not None:
                    sequences[alias] = "".join(parts)

    for entry in (record.get("sequences") or {}).get("entries") or []:
        if entry.pop("sequence_digest", None) is not None:
            entry["sequence"] = sequences[entry["alias"]]
            entry.pop("length")
        elif "length" in entry:
            # 配列の無い entry の長さは、v3 の Entry に置く場所が無い。黙って落とさない。
            raise PackageError(
                f"entry {_quote(str(entry.get('alias')))} has a length but no sequence; v3 cannot hold it"
            )
    record["schema_version"] = V3_SCHEMA_VERSION
    return record


# --- 書く


def pack(record: dict[str, Any], out: Path, fasta_name: str = DEFAULT_FASTA) -> None:
    """v3 の record(1 つの JSON)を、v4 のパッケージにして out に書く。渡した record は書き換えない。

    list は JSON Lines に、entry の sequence は FASTA に移し、entry には length と sequence_digest を書く。
    配列の中の ASCII の空白と改行は除く。書けないものがあれば、何も書かずに PackageError を上げる。
    書いたものは check してから out に置く。
    """
    if not isinstance(record, dict):
        raise PackageError("a record is a JSON object")
    version = record.get("schema_version")
    if version is not None and version != V3_SCHEMA_VERSION:
        raise PackageError(f"not a v3 record: schema_version is {_quote(str(version))}")
    try:
        v3.DdbjRecord.model_validate(record, strict=True)
    except ValidationError as e:
        raise PackageError(f"not a v3 record: {_validation_problem('the record', e)}") from e
    record = json.loads(json.dumps(record))
    record["schema_version"] = SCHEMA_VERSION
    collections = {name: _take(record, location) for name, (location, _) in COLLECTIONS.items()}
    entries = collections[ENTRIES_NAME]
    with_sequence = [entry for entry in entries if entry.get("sequence") is not None]

    _check_packable(with_sequence, fasta_name)

    # 途中で失敗しても、書きかけのパッケージを out に残さない。
    fd, temporary = tempfile.mkstemp(dir=out.parent, prefix=f".{out.name}.", suffix=".tmp")
    os.close(fd)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as package:
            package.writestr(zipfile.ZipInfo(MIMETYPE_NAME), MIMETYPE, compress_type=zipfile.ZIP_STORED)
            # record.json は配列に拠らないので、mimetype のすぐ後に置く。流して読む側が先に読める。
            package.writestr(RECORD_NAME, _dumps(record, indent=2) + b"\n")

            if with_sequence:
                _write_fasta(package, fasta_name, with_sequence)
            for entry in entries:
                entry.pop("sequence", None)

            # entries.jsonl の digest は、配列を書いた後でしか分からない。
            for name, objects in collections.items():
                if objects:
                    with package.open(name, "w", force_zip64=True) as member:
                        for obj in objects:
                            member.write(_dumps(obj) + b"\n")

        _verify(Path(temporary))
        _settle(Path(temporary))
        Path(temporary).replace(out)
    except (ValueError, UnicodeError) as e:
        Path(temporary).unlink(missing_ok=True)
        raise PackageError(f"cannot write the record as JSON: {e}") from e
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def _dumps(obj: Any, indent: int | None = None) -> bytes:
    # NaN と Infinity は JSON(RFC 8259)に無い。
    separators = None if indent else (",", ":")
    return json.dumps(obj, ensure_ascii=False, allow_nan=False, indent=indent, separators=separators).encode("utf-8")


def _verify(path: Path) -> None:
    if problems := check(path):
        raise PackageError("; ".join(problems[:10]))


def _settle(path: Path) -> None:
    """置く前にディスクに書き切り、普通に作ったファイルと同じ権限にする(mkstemp は 0600 で作る)。"""
    with path.open("rb+") as f:
        os.fsync(f.fileno())
    umask = os.umask(0)  # umask を知る方法はこれしか無い。スレッドから同時に pack するなら、呼ぶ側で守る
    os.umask(umask)
    path.chmod(0o666 & ~umask)


def _write_atomically(out: Path, data: bytes) -> None:
    fd, temporary = tempfile.mkstemp(dir=out.parent, prefix=f".{out.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        _settle(Path(temporary))
        Path(temporary).replace(out)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def _write_fasta(package: zipfile.ZipFile, name: str, entries: list[dict[str, Any]]) -> None:
    # 大きさを知らずに流して書くので、ZIP64 にしておく。
    with package.open(name, "w", force_zip64=True) as fasta:
        for entry in entries:
            sequence = ASCII_WHITESPACE.sub("", entry["sequence"])
            entry["length"] = len(sequence)
            entry["sequence_digest"] = sequence_digest([sequence])
            fasta.write(f">{entry['alias']}\n".encode("ascii"))
            for start in range(0, len(sequence), FASTA_WIDTH):
                fasta.write(f"{sequence[start : start + FASTA_WIDTH]}\n".encode("ascii"))


def _check_packable(with_sequence: list[dict[str, Any]], fasta_name: str) -> None:
    if not FASTA_NAME.fullmatch(fasta_name) or not _is_inside(fasta_name):
        raise PackageError(f"cannot write the sequences to {fasta_name!r}; it goes under sequences/ and ends with .fa")

    aliases: Counter[str] = Counter()
    for entry in with_sequence:
        alias = entry.get("alias")
        if not isinstance(alias, str) or not _is_alias(alias):
            raise PackageError(
                f"an entry with a sequence needs an alias of printable ASCII without spaces, up to {MAX_HEADER}: "
                f"{_quote(str(alias))}"
            )
        aliases[alias] += 1

        sequence = entry["sequence"]
        if not isinstance(sequence, str) or not LETTERS.fullmatch(ASCII_WHITESPACE.sub("", sequence)):
            raise PackageError(f"{alias}: the sequence has characters other than ASCII letters")

    if repeated := sorted(alias for alias, n in aliases.items() if n > 1):
        raise PackageError(f"entries share an alias: {', '.join(repeated)}")


def _take(record: dict[str, Any], location: tuple[str, ...]) -> list[dict[str, Any]]:
    """record から location の list を取り除いて返す。

    後に残る入れ物が空なら、それも除く(元から空だったものも)。空は無いのと同じ。
    """
    *parents, key = location
    holder: Any = record
    for parent in parents:
        holder = holder.get(parent)
        if holder is None:
            return []
        if not isinstance(holder, dict):
            raise PackageError(f"{parent} is not an object")
    objects = holder.pop(key, None)
    if objects is None:
        objects = []
    if not isinstance(objects, list) or not all(isinstance(obj, dict) for obj in objects):
        raise PackageError(f"{'.'.join(location)} is not a list of objects")
    if parents and not holder:
        record.pop(parents[0], None)
    return objects


def _place(record: dict[str, Any], location: tuple[str, ...], objects: list[dict[str, Any]]) -> None:
    *parents, key = location
    holder = record
    for parent in parents:
        holder = holder.setdefault(parent, {})
    holder[key] = objects


def _open(path: Path) -> zipfile.ZipFile:
    if not path.is_file() or not zipfile.is_zipfile(path):
        raise PackageError(f"{path}: not a zip")
    try:
        package = zipfile.ZipFile(path)
    except READ_ERRORS as e:
        raise PackageError(f"{path}: not a zip: {e}") from e
    if not _has(package, RECORD_NAME):
        package.close()
        raise PackageError(f"{path}: no {RECORD_NAME}")
    return package


def _read_record_json(package: zipfile.ZipFile) -> bytes:
    try:
        with package.open(RECORD_NAME) as member:
            data = member.read(MAX_RECORD + 1)
    except READ_ERRORS as e:
        raise PackageError(f"{RECORD_NAME} cannot be read: {e}") from e
    if len(data) > MAX_RECORD:
        raise PackageError(f"{RECORD_NAME}: longer than {MAX_RECORD} bytes")
    return data


# --- JSON を読む


def _has(package: zipfile.ZipFile, name: str) -> bool:
    try:
        package.getinfo(name)
    except KeyError:
        return False
    return True


def _parse(where: str, data: bytes, model: type[Model], problems: _Problems) -> Model | None:
    """UTF-8 の JSON のオブジェクト 1 つを、モデルに合わせて読む。合わなければ問題を 1 つ挙げて None。"""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        problems.add(f"{where}: not UTF-8: {e.reason}")
        return None
    if text.startswith("\ufeff"):
        problems.add(f"{where}: begins with a byte order mark")
        return None
    try:
        obj = _loads(text)
    except (ValueError, RecursionError) as e:
        problems.add(f"{where}: not JSON: {_quote(str(e))}")
        return None
    if not isinstance(obj, dict):
        problems.add(f"{where}: not a JSON object")
        return None
    try:
        # 型を読み替えない("4" や true を長さとして受けない)。同じ record は同じ JSON で書かれる。
        return model.model_validate(obj, strict=True)
    except ValidationError as e:
        problems.add(_validation_problem(where, e))
        return None


def _loads(text: str) -> Any:
    """I-JSON (RFC 7493) の JSON を読む。I-JSON でなければ ValueError。"""
    obj = json.loads(
        text,
        parse_constant=_reject_constant,
        parse_float=_interoperable_float,
        parse_int=_interoperable_int,
        object_pairs_hook=_unique_keys,
    )
    # \ud800 のように書いた、対になっていないサロゲートは UTF-8 にできない(I-JSON で断るもの)。
    json.dumps(obj, ensure_ascii=False).encode("utf-8")
    return obj


def _strict(where: str, data: bytes, model: type[Model]) -> Model:
    problems = _Problems(where)
    parsed = _parse(where, data, model, problems)
    if parsed is None:
        raise PackageError(problems.items[0])
    return parsed


def _reject_constant(name: str) -> None:
    raise ValueError(f"{name} is not JSON")


def _interoperable_float(text: str) -> float:
    """I-JSON の数: 倍精度より大きいか精度の高い数は、読む側によって値が変わるので受けない (RFC 7493 §2.2)。

    有効数字 (前後の 0 を除いた桁) が 17 桁を超えるものと、倍精度の範囲を外れるもの (1e400、1e-400) を断る。
    17 桁までなら、倍精度の最も短い表記でなくても受ける (0.10000000000000001、1.10、1E+2)。
    """
    value = float(text)
    exact = Decimal(text)
    if value in (float("inf"), float("-inf")) or (value == 0 and exact != 0):
        raise ValueError(f"{_quote(text)} is out of range")
    if len(exact.normalize().as_tuple().digits) > MAX_SIGNIFICANT_DIGITS:
        raise ValueError(f"{_quote(text)} has more significant digits than a double holds")
    return value


def _interoperable_int(text: str) -> int:
    """I-JSON の整数: ±(2**53 - 1) を超えるものは、倍精度で読む側が正しく読めないので受けない。"""
    value = int(text)
    if abs(value) > MAX_SAFE_INTEGER:
        raise ValueError(f"{_quote(text)} is out of range")
    return value


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    keys = [key for key, _ in pairs]
    if len(set(keys)) != len(keys):
        repeated = next(key for key in keys if keys.count(key) > 1)
        raise ValueError(f"the key {_quote(repeated)} appears twice")
    return dict(pairs)


def _validation_problem(where: str, error: ValidationError) -> str:
    """1 つの JSON の誤りを 1 行にする。誤りの数が多ければ、一覧を作らず数だけを書く(一覧はメモリを食う)。"""
    count = error.error_count()
    if count > MAX_PROBLEMS_PER_FILE:
        return f"{where}: {count} errors"
    first = error.errors(include_url=False, include_input=False, include_context=False)[0]
    location = _quote(".".join(str(part) for part in first["loc"]))
    message = f"{where}: {location}: {first['msg']}" if location else f"{where}: {first['msg']}"
    return f"{message} (and {count - 1} more)" if count > 1 else message


def _lines(member: IO[bytes], problems: _Problems) -> Iterator[tuple[int, bytes]]:
    """JSON Lines を 1 行ずつ返す。MAX_LINE を超える行は読み飛ばして問題にする。"""
    number = 0
    while True:
        line = member.readline(MAX_LINE + 3)  # 行末の CRLF と、超えたことを知る 1 バイト
        if not line:
            return
        number += 1
        body = line[:-2] if line.endswith(b"\r\n") else line[:-1] if line.endswith(b"\n") else line
        if len(body) > MAX_LINE:
            problems.add(f"{problems.name}:{number}: longer than {MAX_LINE} bytes")
            if not line.endswith(b"\n"):
                while (rest := member.readline(CHUNK_SIZE)) and not rest.endswith(b"\n"):
                    pass
            continue
        if b"\r" in body:
            problems.add(f"{problems.name}:{number}: a CR that does not end the line")
            continue
        if not body.strip():
            problems.add(f"{problems.name}:{number}: an empty line")
            continue
        yield number, body


# --- check の中身


class _Problems:
    """1 つのファイルについての問題。MAX_PROBLEMS_PER_FILE を超えた分は数だけ数える。"""

    def __init__(self, name: str) -> None:
        self.name = name
        self.items: list[str] = []
        self.overflow = 0
        self.last: str | None = None

    def add(self, problem: str) -> None:
        if len(self.items) < MAX_PROBLEMS_PER_FILE:
            self.items.append(problem)
        else:
            self.overflow += 1

    def fatal(self, problem: str) -> None:
        """読めなくなったこと。上限に掛けず、必ず最後に挙げる。"""
        self.last = problem

    def all(self) -> list[str]:
        items = [*self.items, f"{self.name}: and {self.overflow} more"] if self.overflow else list(self.items)
        return [*items, self.last] if self.last else items


def check(path: Path) -> list[str]:
    """パッケージが docs/v4-schema.md の約束どおりかを確かめ、外れているものを挙げる。"""
    if not path.is_file() or not zipfile.is_zipfile(path):
        return [f"{path.name}: not a zip"]

    problems = _check_start(path)

    try:
        package = zipfile.ZipFile(path)
    except READ_ERRORS as e:
        return [*problems, f"{path.name}: not a zip: {e}"]

    with package:
        # 先頭の mimetype が目次にも同じに載っているか。先頭が既に違うなら、重ねて挙げない。
        member_problems, unreadable = _check_members(package, check_mimetype=not problems)
        problems += member_problems

        names = set(package.namelist())

        def readable(name: str) -> bool:
            return name in names and name not in unreadable

        if readable(RECORD_NAME):
            problems += _check_record(package)

        expected: dict[str, tuple[int | None, str]] = {}
        for name in COLLECTIONS:
            if readable(name):
                problems += _check_collection(package, name, expected)

        fasta_files = sorted(name for name in names if FASTA_NAME.fullmatch(name) and readable(name))
        problems += _check_sequences(package, expected, fasta_files)
        return problems


def _check_start(path: Path) -> list[str]:
    """ファイルの先頭が、無圧縮で余計なもののない mimetype であることを確かめる。

    zip の目次の順ではなく、ファイルの中の位置を見る。先頭の数十バイトで何のファイルかが分かるように。
    """
    with path.open("rb") as f:
        head = f.read(LOCAL_HEADER.size + len(MIMETYPE_NAME) + len(MIMETYPE))

    if len(head) < LOCAL_HEADER.size:
        return [f"the first member is not {MIMETYPE_NAME}"]

    signature, _, flags, method, _, _, _, compressed, size, name_length, extra_length = LOCAL_HEADER.unpack_from(head)
    name = head[LOCAL_HEADER.size : LOCAL_HEADER.size + name_length]

    if signature != LOCAL_HEADER_SIGNATURE or name != MIMETYPE_NAME.encode("ascii"):
        return [f"the first member is not {MIMETYPE_NAME}"]
    if method != zipfile.ZIP_STORED:
        return [f"{MIMETYPE_NAME} is compressed"]
    if extra_length or flags & DATA_DESCRIPTOR_FLAG:
        return [f"{MIMETYPE_NAME} has an extra field or a data descriptor"]

    content = head[LOCAL_HEADER.size + name_length :]
    if compressed != size or size != len(MIMETYPE) or content != MIMETYPE.encode("ascii"):
        return [f"{MIMETYPE_NAME} is not {MIMETYPE}"]
    return []


def _check_members(package: zipfile.ZipFile, *, check_mimetype: bool) -> tuple[list[str], set[str]]:
    """メンバーの名前、種類、圧縮、暗号化を確かめる。読めないメンバーの名前も返す(中を読まないために)。"""
    infos = package.infolist()
    problems = _Problems("the package")
    if not _has(package, RECORD_NAME):
        problems.add(f"no {RECORD_NAME}")
    unreadable = set()

    mimetype = package.getinfo(MIMETYPE_NAME) if _has(package, MIMETYPE_NAME) else None
    if check_mimetype and (mimetype is None or mimetype.header_offset != 0):
        problems.add(f"{MIMETYPE_NAME} is not the first member in the zip's directory")

    counts = Counter(info.filename for info in infos)
    for name, n in sorted(counts.items()):
        if n > 1:
            problems.add(f"{_quote(name)}: appears more than once")
    # 大文字小文字を区別しないファイルシステムに展開すると重なる。
    folded = Counter(name.casefold() for name in counts)
    for name in sorted(counts):
        if folded[name.casefold()] > 1:
            problems.add(f"{_quote(name)}: differs from another member only in case")

    for info in infos:
        name = _quote(info.filename)
        if info.is_dir():
            problems.add(f"{name}: a directory")
        elif stat.S_ISLNK(info.external_attr >> 16):
            problems.add(f"{name}: a symbolic link")
        elif info.filename not in RESERVED_NAMES and not FASTA_NAME.fullmatch(info.filename):
            problems.add(f"{name}: not a member of a package")
        if not PRINTABLE_ASCII.fullmatch(info.filename) or not _is_inside(info.filename):
            problems.add(f"{name}: not a relative path of printable ASCII inside the package")
        if info.compress_type not in COMPRESSIONS:
            problems.add(f"{name}: compressed other than by deflate")
            unreadable.add(info.filename)
        if info.flag_bits & ENCRYPTED_FLAG:
            problems.add(f"{name}: encrypted")
            unreadable.add(info.filename)
    return problems.all(), unreadable


def _check_record(package: zipfile.ZipFile) -> list[str]:
    problems = _Problems(RECORD_NAME)
    try:
        data = _read_record_json(package)
    except PackageError as e:
        problems.fatal(str(e))
        return problems.all()

    record = _parse(RECORD_NAME, data, v4.DdbjRecord, problems)
    if record is not None:
        for problem in _record_problems(record):
            problems.add(problem)
    return problems.all()


def _record_problems(record: v4.DdbjRecord) -> list[str]:
    """record.json が v4 であり、JSON Lines に置く list を持たないこと。"""
    problems = []
    if record.schema_version != SCHEMA_VERSION:
        problems.append(f"{RECORD_NAME}: schema_version is not {SCHEMA_VERSION}: {_quote(str(record.schema_version))}")
    dumped = record.model_dump(exclude_none=True)
    for name, (location, _) in COLLECTIONS.items():
        holder: Any = dumped
        for key in location:
            holder = holder.get(key) if isinstance(holder, dict) else None
        if holder is not None:
            problems.append(f"{RECORD_NAME}: {'.'.join(location)} goes in {name}")
    return problems


def _check_collection(package: zipfile.ZipFile, name: str, expected: dict[str, tuple[int | None, str]]) -> list[str]:
    """JSON Lines の各行がモデルに合うかを確かめる。entries.jsonl なら、配列を持つ entry を expected に集める。"""
    _, model = COLLECTIONS[name]
    problems = _Problems(name)
    lines = 0
    try:
        with package.open(name) as member:
            for number, line in _lines(member, problems):
                lines += 1
                obj = _parse(f"{name}:{number}", line, model, problems)
                if isinstance(obj, v4.Entry):
                    _expect(obj, number, expected, problems)
    except READ_ERRORS as e:
        problems.fatal(f"{name}: cannot be read: {e}")
    if lines == 0 and not problems.items and problems.last is None:
        problems.add(f"{name}: empty; an empty list has no file")
    return problems.all()


def _expect(entry: v4.Entry, number: int, expected: dict[str, tuple[int | None, str]], problems: _Problems) -> None:
    if not entry.sequence_digest:
        return
    where = f"{problems.name}:{number}"
    if not entry.alias:
        problems.add(f"{where}: has a sequence_digest but no alias to find its sequence by")
    elif not _is_alias(entry.alias):
        problems.add(
            f"{where}: {_quote(entry.alias)}: an alias with a sequence must be printable ASCII without spaces, "
            f"up to {MAX_HEADER}"
        )
    elif entry.alias in expected:
        problems.add(f"{where}: {_quote(entry.alias)}: two entries have this alias")
    elif entry.length is None:
        problems.add(f"{where}: {_quote(entry.alias)}: has a sequence_digest but no length")
    else:
        # 覚えるのは、確かめた alias だけ。
        expected[entry.alias] = (entry.length, entry.sequence_digest)


def _check_sequences(
    package: zipfile.ZipFile, expected: dict[str, tuple[int | None, str]], files: list[str]
) -> list[str]:
    problems = []
    found: dict[str, str] = {}
    for name in files:
        file_problems = _Problems(name)
        records = 0
        try:
            with package.open(name) as fasta:
                for sequence in _read_fasta(fasta, file_problems):
                    records += 1
                    _compare(sequence, expected, found, file_problems)
        except READ_ERRORS as e:
            file_problems.fatal(f"{name}: cannot be read: {e}")
        if records == 0 and not file_problems.items and file_problems.last is None:
            file_problems.add(f"{name}: no sequences; leave the file out")
        problems += file_problems.all()

    missing = _Problems("the sequences")
    for alias in expected:
        if alias not in found:
            missing.add(f"{_quote(alias)}: no sequence in the package")
    return problems + missing.all()


def _compare(
    sequence: tuple[str | None, int, str, bool],
    expected: dict[str, tuple[int | None, str]],
    found: dict[str, str],
    problems: _Problems,
) -> None:
    alias, length, digest, clean = sequence
    name = problems.name

    if alias is None:
        return  # 見出しが alias として読めない。そう挙げてある
    quoted = _quote(alias)
    if alias not in expected:
        # 覚えておくのは entry が待つ alias だけ。FASTA の見出しの数でメモリを使わないように。
        problems.add(f"{name}: {quoted}: no entry has this alias and a sequence_digest")
        return
    if alias in found:
        problems.add(f"{name}: {quoted}: also in {found[alias]}")
        return
    found[alias] = name

    if not clean:
        return  # 読めない行を抜いて比べても、食い違いが増えるだけ
    expected_length, expected_digest = expected[alias]
    if expected_length is not None and expected_length != length:
        problems.add(f"{name}: {quoted}: {length} residues, the entry says {expected_length}")
    if expected_digest != digest:
        problems.add(f"{name}: {quoted}: digest {digest}, the entry says {expected_digest}")


class _FastaReader:
    """FASTA を決まった大きさの塊ずつ読む。

    使うメモリは、行の長さにも見出しの長さにもよらず、塊と MAX_HEADER の大きさで決まる。
    """

    def __init__(self, problems: _Problems) -> None:
        self.problems = problems
        self.line = 1
        self.reported_line = 0  # 1 行の問題は 1 度だけ挙げる(長い行は幾つもの塊にまたがる)
        self.at_line_start = True
        self.pending_cr = False  # 塊の終わりの \r。次の塊が \n で始まれば行末
        self.closing = False
        self.header: bytearray | None = None  # 見出しを読んでいる間だけ
        self.header_too_long = False
        self.alias: str | None = None
        self.in_record = False
        self.length = 0
        self.sha512 = hashlib.sha512()
        self.clean = True
        self.done: list[tuple[str | None, int, str, bool]] = []

    def feed(self, chunk: bytes) -> None:
        segments = chunk.split(b"\n")
        last = len(segments) - 1
        for i, segment in enumerate(segments):
            self._segment(segment, ends_line=i < last)

    def close(self) -> None:
        if self.pending_cr:
            self.closing = True
            self._segment(b"", ends_line=False)  # ファイルの最後の \r は行末でない(改行は LF か CRLF)
        if self.header is not None:
            self._end_header()
        self._finish()

    def _segment(self, segment: bytes, *, ends_line: bool) -> None:
        if self.pending_cr:
            self.pending_cr = False
            segment = b"\r" + segment  # 行末の \r なら、すぐ下で除かれる
        if ends_line and segment.endswith(b"\r"):
            segment = segment[:-1]
        elif not ends_line and segment.endswith(b"\r") and not self.closing:
            segment, self.pending_cr = segment[:-1], True

        if self.at_line_start and segment.startswith(b">"):
            self._finish()
            self.header = bytearray(segment[1 : MAX_HEADER + 2])
            self.header_too_long = len(segment) - 1 > MAX_HEADER
        elif self.header is not None:
            room = MAX_HEADER + 1 - len(self.header)
            if room > 0:
                self.header += segment[:room]
            self.header_too_long = self.header_too_long or len(segment) > room
        else:
            self._data(segment)

        if segment or ends_line:
            self.at_line_start = ends_line
        if ends_line:
            if self.header is not None:
                self._end_header()
            self.line += 1

    def _data(self, data: bytes) -> None:
        if not data:
            return
        if not self.in_record:
            self._report(f"{self.problems.name}:{self.line}: a sequence before any header")
            return
        if not data.isalpha():  # bytes.isalpha は ASCII の英字だけを真とする
            self._report(f"{self.problems.name}:{self.line}: {self._name()}: not only letters")
            self.clean = False
            return
        self.sha512.update(data.upper())
        self.length += len(data)

    def _end_header(self) -> None:
        header = bytes(self.header or b"")
        self.header = None
        alias = header.decode("utf-8", errors="replace")
        if self.header_too_long or not PRINTABLE_ASCII.fullmatch(alias):
            self._report(f"{self.problems.name}:{self.line}: the header is not an alias alone: {_quote(alias)}")
            self.alias = None  # entry に当てない
        else:
            self.alias = alias
        self.in_record = True
        self.length = 0
        self.sha512 = hashlib.sha512()
        self.clean = True

    def _finish(self) -> None:
        if self.in_record:
            self.done.append((self.alias, self.length, _digest(self.sha512), self.clean))
        self.in_record = False
        self.alias = None

    def _name(self) -> str:
        return _quote(self.alias) if self.alias else "(a header that is not an alias)"

    def _report(self, problem: str) -> None:
        if self.reported_line != self.line:
            self.reported_line = self.line
            self.problems.add(problem)


def _read_fasta(fasta: IO[bytes], problems: _Problems) -> Iterator[tuple[str | None, int, str, bool]]:
    """FASTA を読み、配列ごとに (alias, 長さ, digest, 英字でない行が無かったか) を返す。

    見出しが alias として読めなければ、alias は None。
    """
    reader = _FastaReader(problems)
    while chunk := fasta.read(CHUNK_SIZE):
        reader.feed(chunk)
        yield from reader.done
        reader.done.clear()
    reader.close()
    yield from reader.done


def _digest(sha512: Any) -> str:
    return "SQ." + base64.urlsafe_b64encode(sha512.digest()[:24]).decode("ascii")


def _is_alias(alias: str) -> bool:
    return bool(PRINTABLE_ASCII.fullmatch(alias)) and len(alias) <= MAX_HEADER


def _is_inside(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and "\\" not in name
        and not re.match(r"[A-Za-z]:", name)  # Windows のドライブ (C:/x、C:x)
    )


def _quote(text: str) -> str:
    """問題の文に入れる名前。長ければ切り、制御文字などは \\x.. の形にする(端末に生で出さない)。"""
    short = text if len(text) <= MAX_QUOTE else f"{text[:MAX_QUOTE]}..."
    return "".join(c if c.isprintable() else f"\\x{ord(c):02x}" for c in short)


# --- CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DDBJ Record v4 のパッケージ(record.json、JSON Lines、FASTA の zip)")
    commands = parser.add_subparsers(dest="command", required=True)

    check_parser = commands.add_parser("check", help="パッケージが約束どおりかを確かめる")
    check_parser.add_argument("path", type=Path)

    pack_parser = commands.add_parser("pack", help="v3 の record(1 つの JSON)を v4 のパッケージにする")
    pack_parser.add_argument("record", type=Path)
    pack_parser.add_argument("out", type=Path)

    unpack_parser = commands.add_parser("unpack", help="v4 のパッケージを v3 の record(1 つの JSON)に戻す")
    unpack_parser.add_argument("path", type=Path)
    unpack_parser.add_argument("out", type=Path)

    args = parser.parse_args(argv)

    try:
        if args.command == "pack":
            pack(_loads(args.record.read_bytes().decode("utf-8")), args.out)
        elif args.command == "unpack":
            _write_atomically(args.out, _dumps(unpack(args.path), indent=2) + b"\n")
        else:
            problems = check(args.path)
            for problem in problems:
                sys.stderr.write(f"{problem}\n")
            return 1 if problems else 0
    except (PackageError, OSError, ValueError, RecursionError) as e:
        sys.stderr.write(f"{e}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
