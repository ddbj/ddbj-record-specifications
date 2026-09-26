"""DDBJ Record v4 のパッケージ (docs/v4-schema.md) の読み方、確かめ方、作り方。"""

import json
import os
import sys
import typing
import zipfile
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from ddbj_record import package as package_module
from ddbj_record.package import (
    MIMETYPE,
    PackageError,
    check,
    iter_objects,
    load_record,
    main,
    pack,
    read_record,
    sequence_digest,
    unpack,
)
from ddbj_record.schema import v3, v4

PACKAGE_DIR = Path(__file__).resolve().parents[1].joinpath("fixtures", "v4", "packages", "trad_small")
V3_RECORDS_DIR = Path(__file__).resolve().parents[1].joinpath("fixtures", "v3", "records")
FASTA = "sequences/entries.fa"

# 全角の数字。\d は読むが、ASCII の英字や数字としては読めない。
FULLWIDTH_2024 = "".join(chr(0xFF10 + int(digit)) for digit in "2024")


def _read(name: str) -> str:
    return (PACKAGE_DIR / name).read_text(encoding="utf-8")


def _record() -> dict[str, Any]:
    return json.loads(_read("record.json"))  # type: ignore[no-any-return]


def _entries() -> list[dict[str, Any]]:
    return [json.loads(line) for line in _read("entries.jsonl").splitlines()]


def _jsonl(objects: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(obj) + "\n" for obj in objects)


def _zip(path: Path, members: list[tuple[str, bytes]], mimetype: bytes | None = MIMETYPE.encode()) -> Path:
    """members を順に入れた zip を作る。mimetype は無圧縮で先頭に(None なら入れない)。"""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as package:
        if mimetype is not None:
            package.writestr(zipfile.ZipInfo("mimetype"), mimetype, compress_type=zipfile.ZIP_STORED)
        for name, data in members:
            package.writestr(name, data)
    return path


def _members(
    record: dict[str, Any] | None = None, entries: list[dict[str, Any]] | None = None, fasta: str | None = None
) -> list[tuple[str, bytes]]:
    return [
        ("record.json", json.dumps(record if record is not None else _record()).encode()),
        ("entries.jsonl", (_jsonl(entries) if entries is not None else _read("entries.jsonl")).encode()),
        ("features.jsonl", _read("features.jsonl").encode()),
        (FASTA, (fasta if fasta is not None else _read(FASTA)).encode()),
    ]


def _fixture(
    tmp_path: Path,
    record: dict[str, Any] | None = None,
    entries: list[dict[str, Any]] | None = None,
    fasta: str | None = None,
) -> Path:
    """trad_small を、record.json、entries.jsonl、FASTA のどれかを差し替えてパッケージにする。"""
    return _zip(tmp_path / "p.zip", _members(record, entries, fasta))


def _with(tmp_path: Path, name: str | zipfile.ZipInfo, data: str | bytes, **kwargs: Any) -> Path:
    """trad_small に 1 つメンバーを足したパッケージ。"""
    path = _fixture(tmp_path)
    with zipfile.ZipFile(path, "a") as package:
        package.writestr(name, data, **kwargs)
    return path


def _flip(path: Path, marker: bytes, offset: int = 0) -> Path:
    data = bytearray(path.read_bytes())
    data[data.index(marker) + offset] ^= 0xFF
    path.write_bytes(bytes(data))
    return path


def _broken_fasta(tmp_path: Path) -> Path:
    """FASTA の CRC が合わないパッケージ。FASTA を読めば BadZipFile になる。"""
    path = tmp_path / "broken.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as package:
        package.writestr(zipfile.ZipInfo("mimetype"), MIMETYPE)
        for name, data in _members():
            package.writestr(name, data)
    return _flip(path, b">pPLH-1", 1)


def _find_all(data: bytes | bytearray, marker: bytes) -> list[int]:
    found, at = [], data.find(marker)
    while at != -1:
        found.append(at)
        at = data.find(marker, at + 1)
    return found


def test_the_digest_is_refgets() -> None:
    # GA4GH VRS の文書にある例。大文字にしてから計る。
    assert sequence_digest(["ACGT"]) == "SQ.aKF498dAxcJAqme6QYQ7EZ07-fiw8Kw2"
    assert sequence_digest(["ac", "gt"]) == "SQ.aKF498dAxcJAqme6QYQ7EZ07-fiw8Kw2"


def test_the_example_package_is_valid(tmp_path: Path) -> None:
    assert check(_fixture(tmp_path)) == []


# --- 読む


def test_the_record_is_read_without_the_lists_or_the_sequences(tmp_path: Path) -> None:
    record = read_record(_broken_fasta(tmp_path))

    assert record.schema_version == "v4"
    assert record.sequences is None
    assert record.features is None


def test_a_list_is_read_one_line_at_a_time(tmp_path: Path) -> None:
    path = _fixture(tmp_path)

    assert [entry.alias for entry in iter_objects(path, "entries.jsonl")] == ["chromosome", "pPLH-1"]
    assert list(iter_objects(path, "samples.jsonl")) == []
    with pytest.raises(PackageError, match="not a list"):
        list(iter_objects(path, "notes.jsonl"))


def test_the_whole_record_can_be_loaded(tmp_path: Path) -> None:
    record = load_record(_fixture(tmp_path))

    assert record.sequences is not None
    assert [entry.alias for entry in record.sequences.entries or []] == ["chromosome", "pPLH-1"]
    assert [feature.type for feature in record.features or []] == ["CDS"]


@pytest.mark.parametrize(
    "samples",
    ['{"alias":"s1"}\n\n{"alias":"s3"}\n', '{"alias":"s1"}\n{"colour":"red"}\n'],
    ids=["an empty line", "a line that is not a sample"],
)
def test_readers_refuse_a_line_rather_than_skip_it(tmp_path: Path, samples: str) -> None:
    # 飛ばすと、後の行の位置(relation の index)がずれる。
    path = _with(tmp_path, "samples.jsonl", samples)

    with pytest.raises(PackageError, match=r"samples\.jsonl:2"):
        list(iter_objects(path, "samples.jsonl"))
    with pytest.raises(PackageError):
        load_record(path)


def test_a_json_file_is_not_a_package(tmp_path: Path) -> None:
    path = tmp_path / "record.json"
    path.write_text(json.dumps({"schema_version": "v4", "projects": [{"title": "t"}]}), encoding="utf-8")

    assert check(path) == ["record.json: not a zip"]
    with pytest.raises(PackageError, match="not a zip"):
        read_record(path)


# --- record.json と JSON Lines


def test_record_json_holds_no_lists(tmp_path: Path) -> None:
    record = _record()
    record["samples"] = []
    record["sequences"] = {"entries": _entries()}

    problems = check(_fixture(tmp_path, record=record))

    assert "record.json: samples goes in samples.jsonl" in problems
    assert "record.json: sequences.entries goes in entries.jsonl" in problems


def test_each_line_is_an_object_of_its_list(tmp_path: Path) -> None:
    samples = '{"alias":"s1"}\n{"alias":"s2","colour":"red"}\n\nnot json\n[1]\n{"alias":"s6"}\r\r\n'
    problems = check(_with(tmp_path, "samples.jsonl", samples))

    assert "samples.jsonl:2: colour: Extra inputs are not permitted" in problems
    assert "samples.jsonl:3: an empty line" in problems
    assert any(problem.startswith("samples.jsonl:4: not JSON") for problem in problems)
    assert "samples.jsonl:5: not a JSON object" in problems
    assert "samples.jsonl:6: a CR that does not end the line" in problems


@pytest.mark.parametrize(
    ("data", "problem"),
    [
        (b'{"alias":"s1"}\n{"alias":NaN}\n', "samples.jsonl:2: not JSON"),
        ('﻿{"alias":"s1"}\n'.encode(), "samples.jsonl:1: begins with a byte order mark"),
        (b'{"alias":"s\xff"}\n', "samples.jsonl:1: not UTF-8"),
    ],
    ids=["NaN", "BOM", "not UTF-8"],
)
def test_a_line_is_strict_json_in_utf8(tmp_path: Path, data: bytes, problem: str) -> None:
    assert any(p.startswith(problem) for p in check(_with(tmp_path, "samples.jsonl", data)))


def test_an_empty_list_has_no_file(tmp_path: Path) -> None:
    assert "samples.jsonl: empty; an empty list has no file" in check(_with(tmp_path, "samples.jsonl", ""))


def test_a_line_too_long_is_skipped_and_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(package_module, "MAX_LINE", 40)
    samples = '{"alias":"s1"}\n{"alias":"' + "x" * 100 + '"}\n{"alias":"s3"}\n'

    problems = [p for p in check(_with(tmp_path, "samples.jsonl", samples)) if p.startswith("samples.jsonl")]

    assert problems == ["samples.jsonl:2: longer than 40 bytes"]


def test_a_line_with_many_errors_is_counted_not_listed(tmp_path: Path) -> None:
    # 誤りの一覧は、誤りの数だけメモリを食う。
    samples = json.dumps({"alias": "s1", "attributes": [1] * 1000}) + "\n"

    assert check(_with(tmp_path, "samples.jsonl", samples)) == ["samples.jsonl:1: 1000 errors"]


def test_record_json_has_a_size_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(package_module, "MAX_RECORD", 20)

    assert "record.json: longer than 20 bytes" in check(_fixture(tmp_path))
    with pytest.raises(PackageError, match="longer than"):
        read_record(_fixture(tmp_path))


def test_a_broken_record_json_does_not_stop_the_rest(tmp_path: Path) -> None:
    assert check(_fixture(tmp_path, record={"schema_version": "v4", "colour": "red"})) == [
        "record.json: colour: Extra inputs are not permitted"
    ]

    path = _zip(tmp_path / "q.zip", [("record.json", b"{}"), ("samples.jsonl", b'{"colour":"red"}\n')])
    assert "samples.jsonl:1: colour: Extra inputs are not permitted" in check(path)


def test_long_names_are_quoted_short(tmp_path: Path) -> None:
    samples = json.dumps({"alias": "s1", "x" * 10_000: 1}) + "\n"

    problems = check(_with(tmp_path, "samples.jsonl", samples))

    assert len(problems) == 1
    assert len(problems[0]) < 200


def test_projects_stay_in_record_json(tmp_path: Path) -> None:
    # 1 つの登録の project は数十までなので、JSON Lines に出さない。
    out = tmp_path / "dra.ddbj.zip"

    pack({"schema_version": "v3", "projects": [{"alias": f"study-{i}"} for i in range(3)]}, out)

    assert check(out) == []
    with zipfile.ZipFile(out) as package:
        assert package.namelist() == ["mimetype", "record.json"]
    assert [project.alias for project in read_record(out).projects or []] == ["study-0", "study-1", "study-2"]


# --- zip として


@pytest.mark.parametrize(
    ("mimetype", "problem"),
    [
        (None, "the first member is not mimetype"),
        (b"application/zip", f"mimetype is not {MIMETYPE}"),
        (MIMETYPE.encode() + b"\n", f"mimetype is not {MIMETYPE}"),
    ],
)
def test_the_mimetype_comes_first_and_says_what_this_is(tmp_path: Path, mimetype: bytes | None, problem: str) -> None:
    path = _zip(tmp_path / "p.zip", [("record.json", json.dumps({"schema_version": "v4"}).encode())], mimetype)

    assert check(path) == [problem]


def test_a_compressed_mimetype_is_a_problem(tmp_path: Path) -> None:
    path = tmp_path / "p.zip"
    with zipfile.ZipFile(path, "w") as package:
        package.writestr("mimetype", MIMETYPE, compress_type=zipfile.ZIP_DEFLATED)
        package.writestr("record.json", json.dumps({"schema_version": "v4"}))

    assert check(path) == ["mimetype is compressed"]


def test_the_mimetype_is_physically_first(tmp_path: Path) -> None:
    # 目次の順ではなく、ファイルの中の位置で見る。record.json を先に書き、目次だけ入れ替えたもの。
    path = tmp_path / "p.zip"
    with zipfile.ZipFile(path, "w") as package:
        package.writestr("record.json", json.dumps({"schema_version": "v4"}))
        package.writestr(zipfile.ZipInfo("mimetype"), MIMETYPE)
        package.filelist.reverse()

    assert check(path)[0] == "the first member is not mimetype"


def test_the_mimetype_is_also_first_in_the_directory(tmp_path: Path) -> None:
    # 先頭に mimetype のローカルヘッダーだけを足し、目次には載せない。
    inner = _zip(tmp_path / "inner.zip", [("record.json", json.dumps({"schema_version": "v4"}).encode())], None)
    head = _zip(tmp_path / "head.zip", [])
    size = 30 + len("mimetype") + len(MIMETYPE)
    path = tmp_path / "p.zip"
    path.write_bytes(head.read_bytes()[:size] + inner.read_bytes())

    assert "mimetype is not the first member in the zip's directory" in check(path)


def test_the_mimetype_has_no_extra_field(tmp_path: Path) -> None:
    # Info-ZIP の zip は、既定で時刻の extra field を付ける。
    info = zipfile.ZipInfo("mimetype")
    info.extra = b"UT\x05\x00\x03\x00\x00\x00\x00"
    path = tmp_path / "p.zip"
    with zipfile.ZipFile(path, "w") as package:
        package.writestr(info, MIMETYPE)
        package.writestr("record.json", json.dumps({"schema_version": "v4"}))

    assert check(path) == ["mimetype has an extra field or a data descriptor"]


def test_the_mimetype_has_no_data_descriptor_and_says_its_size(tmp_path: Path) -> None:
    path = _zip(tmp_path / "p.zip", [("record.json", json.dumps({"schema_version": "v4"}).encode())])
    data = bytearray(path.read_bytes())
    data[6] |= 0x08  # 汎用フラグの data descriptor
    (tmp_path / "flag.zip").write_bytes(bytes(data))

    data = bytearray(path.read_bytes())
    data[18] += 1  # 圧縮後の大きさ
    (tmp_path / "size.zip").write_bytes(bytes(data))

    assert check(tmp_path / "flag.zip")[0] == "mimetype has an extra field or a data descriptor"
    assert check(tmp_path / "size.zip")[0] == f"mimetype is not {MIMETYPE}"


def test_a_member_that_cannot_be_read_is_a_problem_not_an_exception(tmp_path: Path) -> None:
    assert any(f"{FASTA}: cannot be read" in problem for problem in check(_broken_fasta(tmp_path)))


def test_a_broken_deflate_stream_is_a_problem(tmp_path: Path) -> None:
    path = _fixture(tmp_path)
    with zipfile.ZipFile(path) as package:
        info = package.getinfo(FASTA)
    data = bytearray(path.read_bytes())
    data[info.header_offset + 30 + len(FASTA)] = 0xFF  # deflate の最初のバイト
    path.write_bytes(bytes(data))

    assert any(problem.startswith(f"{FASTA}: cannot be read") for problem in check(path))


def test_a_broken_directory_is_a_problem(tmp_path: Path) -> None:
    path = _flip(_fixture(tmp_path), b"PK\x01\x02", 1)  # 目次の最初の署名

    problems = check(path)

    assert problems
    assert all(isinstance(problem, str) for problem in problems)
    with pytest.raises(PackageError):
        read_record(path)


def test_a_read_error_is_reported_past_the_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(package_module, "CHUNK_SIZE", 64)
    path = tmp_path / "p.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as package:
        package.writestr(zipfile.ZipInfo("mimetype"), MIMETYPE)
        package.writestr("record.json", _read("record.json"))
        package.writestr(FASTA, "acgt\n" * 3000 + ">end\n")
    _flip(path, b">end", 1)

    problems = check(path)

    # 上限を超えた後に読めなくなっても、そのことは最後に必ず挙がる。
    assert problems[-2].startswith(f"{FASTA}: and ")
    assert problems[-1].startswith(f"{FASTA}: cannot be read")


def test_only_deflate_or_no_compression(tmp_path: Path) -> None:
    path = _with(tmp_path, "samples.jsonl", '{"alias":"s1"}\n', compress_type=zipfile.ZIP_LZMA)

    assert "samples.jsonl: compressed other than by deflate" in check(path)


def test_an_encrypted_member_is_a_problem_and_not_read(tmp_path: Path) -> None:
    path = _fixture(tmp_path)
    with zipfile.ZipFile(path) as package:
        offset = package.getinfo(FASTA).header_offset
    data = bytearray(path.read_bytes())
    data[offset + 6] |= 0x01  # ローカルヘッダー
    name = FASTA.encode()
    entry = next(at for at in _find_all(data, b"PK\x01\x02") if data[at + 46 : at + 46 + len(name)] == name)
    data[entry + 8] |= 0x01  # 目次
    path.write_bytes(bytes(data))

    problems = check(path)

    assert f"{FASTA}: encrypted" in problems
    assert not any("cannot be read" in problem for problem in problems)


@pytest.mark.parametrize(
    ("name", "problem"),
    [
        ("notes.txt", "notes.txt: not a member of a package"),
        ("sequences.fa", "sequences.fa: not a member of a package"),
        ("sequences/a/b.fa", "sequences/a/b.fa: not a member of a package"),
        ("/abs.fa", "/abs.fa: not a relative path of printable ASCII inside the package"),
        ("a\\b.fa", "a\\b.fa: not a relative path of printable ASCII inside the package"),
        ("C:x.fa", "C:x.fa: not a relative path of printable ASCII inside the package"),
        ("a/../../x.fa", "a/../../x.fa: not a relative path of printable ASCII inside the package"),
        ("配列.fa", "配列.fa: not a relative path of printable ASCII inside the package"),
        ("dir/", "dir/: a directory"),
    ],
)
def test_members_are_only_the_package_s(tmp_path: Path, name: str, problem: str) -> None:
    assert problem in check(_with(tmp_path, name, ""))


def test_a_name_appearing_twice_is_a_problem(tmp_path: Path) -> None:
    path = _fixture(tmp_path)
    with zipfile.ZipFile(path, "a") as package, pytest.warns(UserWarning, match="Duplicate name"):
        package.writestr(FASTA, ">x\nacgt\n")

    assert f"{FASTA}: appears more than once" in check(path)


def test_a_symbolic_link_is_a_problem(tmp_path: Path) -> None:
    info = zipfile.ZipInfo("sequences/link.fa")
    info.external_attr = 0o120777 << 16

    assert "sequences/link.fa: a symbolic link" in check(_with(tmp_path, info, "/etc/passwd"))


# --- entry と配列


def test_sequences_can_be_split_across_fasta_files(tmp_path: Path) -> None:
    # 分け方は record に書かない。どう分けても同じ record になる。
    fasta = _read(FASTA)
    at = fasta.index(">pPLH-1")
    members = [
        *_members()[:3],
        ("sequences/chromosome.fa", fasta[:at].encode()),
        ("sequences/plasmid.fa", fasta[at:].encode()),
    ]
    path = _zip(tmp_path / "split.zip", members)

    assert check(path) == []
    assert load_record(path) == load_record(_fixture(tmp_path))


def test_entries_pointing_at_sequences_need_them(tmp_path: Path) -> None:
    path = _zip(tmp_path / "p.zip", _members()[:2])

    assert check(path) == ["chromosome: no sequence in the package", "pPLH-1: no sequence in the package"]


def test_an_entry_with_a_digest_needs_a_good_alias_and_a_length(tmp_path: Path) -> None:
    entries = _entries()
    entries[0]["alias"] = "chromo some"
    del entries[1]["length"]

    problems = check(_fixture(tmp_path, entries=entries))

    assert any(p.startswith("entries.jsonl:1: chromo some: an alias with a sequence must be") for p in problems)
    assert "entries.jsonl:2: pPLH-1: has a sequence_digest but no length" in problems
    assert f"{FASTA}: chromosome: no entry has this alias and a sequence_digest" in problems
    assert not any("no sequence in" in p for p in problems)  # 確かめられなかった alias は待たない


def test_entries_are_found_by_a_unique_alias(tmp_path: Path) -> None:
    entries = _entries()
    entries[1]["alias"] = "chromosome"

    assert "entries.jsonl:2: chromosome: two entries have this alias" in check(_fixture(tmp_path, entries=entries))


def test_a_sequence_must_match_its_entry(tmp_path: Path) -> None:
    problems = check(_fixture(tmp_path, fasta=_read(FASTA).replace("aaagtaa", "aaagtaac")))

    assert len(problems) == 2
    assert problems[0] == f"{FASTA}: pPLH-1: 46 residues, the entry says 45"
    assert problems[1].startswith(f"{FASTA}: pPLH-1: digest SQ.")


def test_the_case_of_a_sequence_does_not_matter(tmp_path: Path) -> None:
    assert check(_fixture(tmp_path, fasta=_read(FASTA).replace("atgtatg", "ATGTATG"))) == []


def test_every_sequence_belongs_to_one_entry_and_every_entry_has_one(tmp_path: Path) -> None:
    fasta = _read(FASTA)
    fasta = fasta[: fasta.index(">pPLH-1")] + ">stray\nacgt\n>chromosome\nacgt\n"

    assert check(_fixture(tmp_path, fasta=fasta)) == [
        f"{FASTA}: stray: no entry has this alias and a sequence_digest",
        f"{FASTA}: chromosome: also in {FASTA}",
        "pPLH-1: no sequence in the package",
    ]


@pytest.mark.parametrize(
    ("fasta", "problem"),
    [
        ("acgt\n>chromosome\n", f"{FASTA}:1: a sequence before any header"),
        (">chromosome description\n", f"{FASTA}:1: the header is not an alias alone: chromosome description"),
        (">chromosome\nacg-t\n", f"{FASTA}:2: chromosome: not only letters"),
        (">chromosome\nacgt\r", f"{FASTA}:2: chromosome: not only letters"),
        (">chromosome\nac\rgt\n", f"{FASTA}:2: chromosome: not only letters"),
        (">chromosome\nacg>t\n", f"{FASTA}:2: chromosome: not only letters"),
        (">chromosome\nac1gt\n", f"{FASTA}:2: chromosome: not only letters"),
        ("  \n>chromosome\nacgt\n", f"{FASTA}:1: a sequence before any header"),
    ],
    ids=[
        "before any header",
        "a description",
        "a hyphen",
        "lone CR at the end",
        "lone CR in a line",
        "> in a line",
        "a digit",
        "spaces before any header",
    ],
)
def test_a_fasta_is_read_strictly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fasta: str, problem: str) -> None:
    for size in (3, 1 << 20):
        monkeypatch.setattr(package_module, "CHUNK_SIZE", size)
        assert problem in check(_fixture(tmp_path, fasta=fasta)), size


def test_a_fasta_reads_the_same_whatever_the_chunk_size(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # 塊の境目が見出しの途中、\r と \n の間、行の途中に来ても同じに読める。
    path = _fixture(tmp_path, fasta="\n" + _read(FASTA).replace("\n", "\r\n") + "\n")

    for size in (1, 2, 3, 7, 64):
        monkeypatch.setattr(package_module, "CHUNK_SIZE", size)
        assert check(path) == [], size


def test_a_sequence_on_one_long_line_is_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(package_module, "CHUNK_SIZE", 1000)
    sequence = "acgt" * 100_000
    entries = _entries()
    entries[1]["length"], entries[1]["sequence_digest"] = len(sequence), sequence_digest([sequence])
    fasta = _read(FASTA)
    fasta = fasta[: fasta.index(">pPLH-1")] + f">pPLH-1\n{sequence}\n"

    assert check(_fixture(tmp_path, entries=entries, fasta=fasta)) == []


def test_a_long_bad_line_is_reported_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(package_module, "CHUNK_SIZE", 16)
    fasta = _read(FASTA).replace("aaagtaa", "aaagt" + "-" * 1000 + "aa")

    assert check(_fixture(tmp_path, fasta=fasta)) == [f"{FASTA}:7: pPLH-1: not only letters"]


def test_problems_are_capped(tmp_path: Path) -> None:
    problems = check(_fixture(tmp_path, fasta="acgt\n" * 500))

    assert problems[-3:] == [
        f"{FASTA}: and 400 more",
        "chromosome: no sequence in the package",
        "pPLH-1: no sequence in the package",
    ]


def test_a_header_only_record_at_the_end(tmp_path: Path) -> None:
    entries = _entries()
    entries[1]["length"], entries[1]["sequence_digest"] = 0, sequence_digest([""])
    fasta = _read(FASTA)
    fasta = fasta[: fasta.index(">pPLH-1")] + ">pPLH-1"  # 改行も無い

    assert check(_fixture(tmp_path, entries=entries, fasta=fasta)) == []


def test_an_overlong_header_is_not_an_alias(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(package_module, "MAX_HEADER", 10)
    fasta = _read(FASTA) + ">" + "x" * 5000 + "\nacgt\n"

    problems = check(_fixture(tmp_path, fasta=fasta))

    assert len(problems) == 1
    assert problems[0].startswith(f"{FASTA}:8: the header is not an alias alone")
    assert len(problems[0]) < 200


# --- pack と unpack(v3 と v4 の間)


def _v3_record() -> dict[str, Any]:
    """trad_small を v3 の形(1 つの JSON で、entry に配列を書いたもの)で。"""
    record = _record()
    record["schema_version"] = "v3"
    fasta = _read(FASTA)
    entries = _entries()
    for entry in entries:
        header = f">{entry['alias']}\n"
        entry["sequence"] = fasta[fasta.index(header) + len(header) :].split(">", 1)[0].replace("\n", "")
        del entry["length"], entry["sequence_digest"]
    record["sequences"] = {"entries": entries}
    record["features"] = [json.loads(line) for line in _read("features.jsonl").splitlines()]
    return record


def test_pack_makes_a_v4_package_from_a_v3_record(tmp_path: Path) -> None:
    record = _v3_record()
    out = tmp_path / "packed.zip"

    pack(record, out)

    assert check(out) == []
    with zipfile.ZipFile(out) as package:
        # record.json は配列に拠らないので、mimetype のすぐ後。
        assert package.namelist() == ["mimetype", "record.json", FASTA, "entries.jsonl", "features.jsonl"]
    assert load_record(out) == load_record(_fixture(tmp_path))
    assert record["schema_version"] == "v3"  # 渡した record は書き換えない
    assert "sequence" in record["sequences"]["entries"][0]


def test_unpack_gives_the_v3_record_back(tmp_path: Path) -> None:
    out = tmp_path / "packed.zip"
    pack(_v3_record(), out)

    assert unpack(out) == _v3_record()


@pytest.mark.parametrize(
    "path",
    [path for path in sorted(V3_RECORDS_DIR.glob("*.json")) if not path.stem.startswith("trad")],
    ids=lambda path: path.stem,
)
def test_every_v3_fixture_without_sequences_goes_there_and_back(tmp_path: Path, path: Path) -> None:
    # Trad の fixture の配列は「ttat...(2277985 bp)...gaa」のような省略で、配列として書けない。
    record = json.loads(path.read_text(encoding="utf-8"))
    out = tmp_path / "p.zip"

    pack(record, out)

    assert check(out) == []
    assert unpack(out) == record


def test_a_record_without_lists_is_a_package_of_record_json_alone(tmp_path: Path) -> None:
    out = tmp_path / "bioproject.ddbj.zip"

    pack({"schema_version": "v3", "projects": [{"title": "t"}]}, out)

    assert check(out) == []
    with zipfile.ZipFile(out) as package:
        assert package.namelist() == ["mimetype", "record.json"]


def test_samples_go_one_per_line(tmp_path: Path) -> None:
    out = tmp_path / "biosample.ddbj.zip"

    pack({"schema_version": "v3", "samples": [{"alias": f"s{i}"} for i in range(3)]}, out)

    assert check(out) == []
    assert read_record(out).samples is None
    assert [sample.alias for sample in iter_objects(out, "samples.jsonl")] == ["s0", "s1", "s2"]


@pytest.mark.parametrize(
    ("entries", "message"),
    [
        ([{"alias": "a", "sequence": "ac>gt"}], "other than ASCII letters"),
        ([{"alias": "a", "sequence": "acgü"}], "other than ASCII letters"),
        ([{"alias": "a", "sequence": FULLWIDTH_2024}], "other than ASCII letters"),
        ([{"alias": "a", "sequence": "ac　gt"}], "other than ASCII letters"),
        ([{"alias": "a b", "sequence": "acgt"}], "needs an alias"),
        ([{"accession": "AB000001.1", "sequence": "acgt"}], "needs an alias"),
        ([{"alias": "a", "sequence": "acgt"}, {"alias": "a", "sequence": "tt"}], "share an alias: a"),
        ([{"alias": "a", "length": 4, "sequence_digest": sequence_digest(["acgt"])}], "not a v3 record"),
    ],
)
def test_pack_refuses_what_it_cannot_write(tmp_path: Path, entries: list[dict[str, Any]], message: str) -> None:
    with pytest.raises(PackageError, match=message):
        pack({"schema_version": "v3", "sequences": {"entries": entries}}, tmp_path / "p.zip")

    assert list(tmp_path.iterdir()) == []  # 書きかけを残さない


@pytest.mark.parametrize(
    ("record", "fasta_name", "message"),
    [
        ({"sequences": {"entries": [{"alias": "a", "sequence": "acgt"}]}}, "record.json", "cannot write"),
        ({"sequences": {"entries": [{"alias": "a", "sequence": "acgt"}]}}, "sequences/../x.fa", "cannot write"),
        ({"sequences": []}, FASTA, "not a v3 record"),
        ({"samples": ["s1"]}, FASTA, "not a v3 record"),
        ({"samples": {}}, FASTA, "not a v3 record"),
        ({"bogus": 1}, FASTA, "bogus"),
        ({"schema_version": "v2.0"}, FASTA, "not a v3 record"),
        # v3 の schema_version に minor は付かない (docs/versioning.md)。
        ({"schema_version": "v3.0"}, FASTA, "not a v3 record"),
        ({"sequences": {"entries": [{"alias": "a", "sequence": "acgt"}]}}, "sequences/.a.fa", "cannot write"),
        ({"experiments": [{"library": {"nominal_sdev": float("nan")}}]}, FASTA, "JSON"),
        ({"projects": [{"title": "\ud800"}]}, FASTA, "JSON"),
    ],
)
def test_pack_refuses_a_record_it_cannot_write(
    tmp_path: Path, record: dict[str, Any], fasta_name: str, message: str
) -> None:
    with pytest.raises(PackageError, match=message):
        pack(record, tmp_path / "p.zip", fasta_name)

    assert list(tmp_path.iterdir()) == []


def test_pack_takes_null_as_absent(tmp_path: Path) -> None:
    pack({"schema_version": "v3", "sequences": None, "samples": None}, tmp_path / "p.zip")

    assert check(tmp_path / "p.zip") == []


def test_pack_refuses_a_record_that_is_not_an_object(tmp_path: Path) -> None:
    with pytest.raises(PackageError, match="JSON object"):
        pack([], tmp_path / "p.zip")  # type: ignore[arg-type]


def test_pack_drops_ascii_whitespace_in_a_sequence(tmp_path: Path) -> None:
    out = tmp_path / "p.zip"

    pack({"schema_version": "v3", "sequences": {"entries": [{"alias": "a", "sequence": "ac\ng t"}]}}, out)

    entry = next(iter_objects(out, "entries.jsonl"))
    assert (entry.length, entry.sequence_digest) == (4, sequence_digest(["acgt"]))


def test_a_packed_file_has_the_usual_permissions(tmp_path: Path) -> None:
    umask = os.umask(0o022)
    try:
        pack({"schema_version": "v3"}, tmp_path / "p.zip")
    finally:
        os.umask(umask)

    assert (tmp_path / "p.zip").stat().st_mode & 0o777 == 0o644


# --- CLI


def test_the_cli_reports_what_is_wrong(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", str(_fixture(tmp_path))]) == 0

    bad = _zip(tmp_path / "bad.zip", [("record.json", b"{}")], mimetype=None)
    assert main(["check", str(bad)]) == 1
    assert "the first member is not mimetype" in capsys.readouterr().err


def test_the_cli_packs_and_unpacks(tmp_path: Path) -> None:
    source = tmp_path / "record.json"
    source.write_text(json.dumps(_v3_record()), encoding="utf-8")

    assert main(["pack", str(source), str(tmp_path / "p.zip")]) == 0
    assert main(["unpack", str(tmp_path / "p.zip"), str(tmp_path / "back.json")]) == 0
    assert json.loads((tmp_path / "back.json").read_text(encoding="utf-8")) == _v3_record()


@pytest.mark.parametrize("content", [None, b"\xff\xfe", b"[" * 100_000], ids=["missing", "not UTF-8", "deeply nested"])
def test_the_cli_reports_a_record_it_cannot_read(tmp_path: Path, content: bytes | None) -> None:
    source = tmp_path / "record.json"
    if content is not None:
        source.write_bytes(content)

    assert main(["pack", str(source), str(tmp_path / "p.zip")]) == 1


@pytest.mark.parametrize(
    ("content", "problem"),
    [
        ('{"schema_version":"v3","schema_version":"v3"}', "appears twice"),
        ('{"schema_version":"v3","experiments":[{"library":{"nominal_sdev":0.100000000000000000001}}]}', "significant"),
    ],
    ids=["duplicate key", "too many significant digits"],
)
def test_the_cli_packs_only_i_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], content: str, problem: str
) -> None:
    # 読む側と同じ約束で読む。同じ key の最後を採ったり、数を黙って丸めたりしない。
    source = tmp_path / "record.json"
    source.write_text(content, encoding="utf-8")

    assert main(["pack", str(source), str(tmp_path / "p.zip")]) == 1
    assert problem in capsys.readouterr().err
    assert not (tmp_path / "p.zip").exists()


# --- 読み直しで足したもの


def _model_of(annotation: Any) -> type[BaseModel]:
    """`list[X] | None` や `X | None` の X。"""
    for arg in typing.get_args(annotation) or (annotation,):
        if arg is type(None):
            continue
        inner = typing.get_args(arg)
        found = inner[0] if inner else arg
        assert isinstance(found, type)
        assert issubclass(found, BaseModel)
        return found
    raise AssertionError(annotation)


def test_v4_covers_every_part_of_a_v3_record() -> None:
    # v4 の DdbjRecord は v3 のものを継承しない(v4 の record を v3 として受けさせない)ので、欄を写している。
    # v3 に欄が増えたら、v4 にも足す。数に上限の無い list なら JSON Lines にも。
    assert list(v4.DdbjRecord.model_fields) == list(v3.DdbjRecord.model_fields)
    assert list(v4.Sequences.model_fields) == list(v3.Sequences.model_fields)
    assert set(v4.Entry.model_fields) == (set(v3.Entry.model_fields) - {"sequence"}) | {"length", "sequence_digest"}

    # 名前だけでなく型も。v4 で変わるのは、Entry を含む sequences と entries だけ。
    for v4_model, v3_model, changed in (
        (v4.DdbjRecord, v3.DdbjRecord, {"sequences"}),
        (v4.Sequences, v3.Sequences, {"entries"}),
        (v4.Entry, v3.Entry, {"sequence", "length", "sequence_digest"}),
    ):
        for name in set(v3_model.model_fields) & set(v4_model.model_fields) - changed:
            v4_field, v3_field = v4_model.model_fields[name], v3_model.model_fields[name]
            assert (v4_field.annotation, v4_field.metadata) == (v3_field.annotation, v3_field.metadata), name

    # JSON Lines の各行のモデルは、その list の要素の型。
    for name, (location, model) in package_module.COLLECTIONS.items():
        owner: type[BaseModel] = v4.DdbjRecord
        for part in location[:-1]:
            owner = _model_of(owner.model_fields[part].annotation)
        assert _model_of(owner.model_fields[location[-1]].annotation) is model, name

    top_level_lists = {
        name for name, field in v3.DdbjRecord.model_fields.items() if str(field.annotation).startswith("list[")
    }
    collections = {location[0] for location, _ in package_module.COLLECTIONS.values() if len(location) == 1}
    # projects は数が限られるので record.json に残す (docs/v4-schema.md)。トップレベルの list が増えたら、
    # どちらに置くかを決めてここか COLLECTIONS に足す。
    assert top_level_lists == collections | {"projects"}
    assert not isinstance(v4.DdbjRecord(), v3.DdbjRecord)


@pytest.mark.parametrize(
    ("line", "problem"),
    [
        ('{"alias":"s1","attributes":[{"name":"n","value":"v"}],"x":1e400}', "out of range"),
        ('{"alias":"\\ud800"}', "not JSON"),
        ('{"alias":"a","alias":"b"}', "appears twice"),
        ('{"alias":"s1","x":9007199254740992}', "out of range"),
        ('{"alias":"s1","x":-9007199254740992}', "out of range"),
        ('{"alias":"s1","x":1.00000000000000000001}', "more significant digits than a double holds"),
        ('{"alias":"s1","x":0.123456789012345678}', "more significant digits than a double holds"),
        ('{"alias":"s1","x":1e-400}', "out of range"),
    ],
    ids=[
        "infinity",
        "lone surrogate",
        "duplicate key",
        "integer too large",
        "integer too small",
        "19 significant digits",
        "18 significant digits",
        "underflow",
    ],
)
def test_a_line_is_i_json(tmp_path: Path, line: str, problem: str) -> None:
    problems = check(_with(tmp_path, "samples.jsonl", line + "\n"))

    assert any(problem in p for p in problems), problems


@pytest.mark.parametrize("length", ['"45"', "45.0", "true"])
def test_types_are_not_read_as_other_types(tmp_path: Path, length: str) -> None:
    entries = _read("entries.jsonl").replace('"length":45', f'"length":{length}')
    members = [*_members()[:1], ("entries.jsonl", entries.encode()), *_members()[2:]]

    problems = check(_zip(tmp_path / "p.zip", members))

    assert any(p.startswith("entries.jsonl:2: length:") for p in problems), problems


def test_record_json_is_v4(tmp_path: Path) -> None:
    record = _record()
    record["schema_version"] = "v3"

    assert "record.json: schema_version is not v4: v3" in check(_fixture(tmp_path, record=record))
    with pytest.raises(PackageError, match="schema_version"):
        read_record(_fixture(tmp_path, record=record))


def test_readers_refuse_lists_in_record_json(tmp_path: Path) -> None:
    record = _record()
    record["samples"] = [{"alias": "s1"}]

    with pytest.raises(PackageError, match=r"goes in samples\.jsonl"):
        read_record(_fixture(tmp_path, record=record))


def test_readers_refuse_an_empty_list_file(tmp_path: Path) -> None:
    with pytest.raises(PackageError, match="empty"):
        list(iter_objects(_with(tmp_path, "samples.jsonl", ""), "samples.jsonl"))


def test_iter_objects_stops_at_a_bad_line(tmp_path: Path) -> None:
    path = _with(tmp_path, "samples.jsonl", '{"alias":"s1"}\n{"colour":"red"}\n{"alias":"s3"}\n')
    objects = iter_objects(path, "samples.jsonl")

    assert next(objects).alias == "s1"
    with pytest.raises(PackageError):
        next(objects)


@pytest.mark.parametrize(
    ("name", "problem"),
    [
        ("sequences/.hidden.fa", "sequences/.hidden.fa: not a member of a package"),
        ("sequences/a:b.fa", "sequences/a:b.fa: not a member of a package"),
        ("sequences/Entries.fa", "sequences/Entries.fa: differs from another member only in case"),
    ],
)
def test_fasta_names_are_portable(tmp_path: Path, name: str, problem: str) -> None:
    assert problem in check(_with(tmp_path, name, ">x\nacgt\n"))


def test_an_empty_fasta_file_is_a_problem(tmp_path: Path) -> None:
    assert "sequences/empty.fa: no sequences; leave the file out" in check(_with(tmp_path, "sequences/empty.fa", ""))


def test_control_characters_are_not_printed_raw(tmp_path: Path) -> None:
    problems = check(_with(tmp_path, "samples.jsonl", '{"alias":"s1","\\u001b[31m":1}\n'))

    assert problems
    assert not any("\x1b" in p for p in problems)


def test_unpack_reads_split_fasta_and_keeps_case(tmp_path: Path) -> None:
    record = _v3_record()
    entry = record["sequences"]["entries"][1]
    entry["sequence"] = entry["sequence"].upper()
    out = tmp_path / "p.zip"
    pack(record, out)
    with zipfile.ZipFile(out) as package:
        parts = {name: package.read(name) for name in package.namelist() if name != "mimetype"}
    fasta = parts.pop(FASTA).decode()
    at = fasta.index(">pPLH-1")
    split = [*parts.items(), ("sequences/1.fa", fasta[:at].encode()), ("sequences/2.fa", fasta[at:].encode())]

    assert unpack(_zip(tmp_path / "split.zip", split)) == record


def test_unpack_refuses_a_package_that_does_not_check(tmp_path: Path) -> None:
    with pytest.raises(PackageError, match="digest"):
        unpack(_fixture(tmp_path, fasta=_read(FASTA).replace("aaagtaa", "aaagtac")))


def test_trad_fixtures_with_real_sequences_go_there_and_back(tmp_path: Path) -> None:
    # Trad の fixture の省略された配列を、短い本物の配列に差し替える。
    for path in sorted(V3_RECORDS_DIR.glob("trad_*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        for i, entry in enumerate(record["sequences"]["entries"]):
            entry["sequence"] = "acgt" * (i + 1)
        out = tmp_path / f"{path.stem}.zip"

        pack(record, out)

        assert check(out) == [], path.stem
        assert unpack(out) == record, path.stem


@pytest.mark.parametrize("number", ["9007199254740991", "-9007199254740991", "0", "-0"])
def test_integers_a_double_holds_are_read(tmp_path: Path, number: str) -> None:
    # I-JSON の範囲の端。
    path = _with(tmp_path, "experiments.jsonl", f'{{"alias":"e1","library":{{"nominal_length":{number}}}}}\n')

    assert check(path) == []
    library = next(iter_objects(path, "experiments.jsonl")).library
    assert library is not None
    assert library.nominal_length == int(number)


@pytest.mark.parametrize(
    "number",
    [
        "0.1",
        "1e2",
        "1E+2",
        "2.5E-3",
        "1.10",
        "-0.0",
        "0E0",
        "5e-324",
        "4.9e-324",
        "0.10000000000000001",
        "1.7976931348623157e308",
        "1.0000000000000000000",  # 後ろの 0 は有効数字に数えない
    ],
)
def test_numbers_of_up_to_17_significant_digits_are_read(tmp_path: Path, number: str) -> None:
    # 倍精度の最も短い表記でなくてもよい (%.17g や Java の Double.toString の書き方)。値は float と同じ。
    path = _with(tmp_path, "experiments.jsonl", f'{{"alias":"e1","library":{{"nominal_sdev":{number}}}}}\n')

    assert check(path) == []
    library = next(iter_objects(path, "experiments.jsonl")).library
    assert library is not None
    assert library.nominal_sdev == float(number)


@pytest.mark.parametrize(
    ("number", "problem"),
    [("9007199254740992", "out of range"), ("1e-400", "out of range"), ("0.100000000000000000001", "significant")],
)
def test_the_number_rule_holds_in_record_json(tmp_path: Path, number: str, problem: str) -> None:
    record = _record()
    record["submission"] = {"gea": {"legacy": {"cibex": {"experiment": {"number_of_hybridizations": 0}}}}}
    text = json.dumps(record).replace('"number_of_hybridizations": 0', f'"number_of_hybridizations": {number}')
    path = _zip(tmp_path / "p.zip", [("record.json", text.encode()), *_members()[1:]])

    assert any(problem in p for p in check(path)), check(path)
    with pytest.raises(PackageError, match=problem):
        read_record(path)


def test_a_too_large_integer_is_not_read(tmp_path: Path) -> None:
    path = _with(tmp_path, "experiments.jsonl", '{"alias":"e1","library":{"nominal_length":18446744073709551616}}\n')

    assert any("out of range" in p for p in check(path))
    with pytest.raises(PackageError, match="out of range"):
        list(iter_objects(path, "experiments.jsonl"))


def test_unpack_refuses_a_length_without_a_sequence(tmp_path: Path) -> None:
    # 配列の無い entry は長さだけを書いてよいが、v3 の Entry には置く場所が無いので、黙って落とさない。
    entries = _entries()
    entries.append({"alias": "gap", "length": 100})
    path = _fixture(tmp_path, entries=entries)

    assert check(path) == []
    with pytest.raises(PackageError, match="v3 cannot hold it"):
        unpack(path)


@pytest.mark.skipif(sys.version_info < (3, 11), reason="typing.get_overloads は 3.11 から")
def test_iter_objects_has_an_overload_for_every_list() -> None:
    names = set()
    for overload in typing.get_overloads(iter_objects):
        annotation = typing.get_type_hints(overload)["name"]
        if annotation is not str:
            names |= set(typing.get_args(annotation))
    assert names == set(package_module.COLLECTIONS)
