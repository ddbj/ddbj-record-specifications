"""tests/fixtures/v3/mapping/*.yml を読んで確かめるテストの共通部品。

対応表の場所は DdbjRecord の中の点区切りの道筋 (`experiments[].pool.members[].sample.id`)。
`[...]` は list の要素、`{...}` は dict の値で、括弧の中と末尾の ` (...)` は読み手のための注記。
`(container)` は、自分では値を持たない入れ物の要素を表す。
"""

import json
import re
from pathlib import Path
from types import NoneType, UnionType
from typing import Any, Union, get_args, get_origin, get_type_hints

import yaml
from pydantic import BaseModel

from ddbj_record.schema.v3 import DdbjRecord

ROOT = Path(__file__).resolve().parents[3]
FIXTURES_V3 = ROOT.joinpath("tests/fixtures/v3")

CONTAINER = "(container)"
SEGMENT = re.compile(r"(\w+)(\[[^\]]*\]|\{[^}]*\})?")
SCALARS = (str, int, float, bool)


def strip_note(location: str) -> str:
    return re.sub(r" \(.*\)$", "", location)


def _unwrap_optional(tp: Any) -> Any:
    if get_origin(tp) in (Union, UnionType):
        args = [a for a in get_args(tp) if a is not NoneType]
        if len(args) != 1:
            raise TypeError(tp)
        return args[0]
    return tp


def resolve(location: str) -> Any:
    """location にある型。モデルに無い場所なら LookupError。"""
    tp: Any = DdbjRecord

    for segment in strip_note(location).split("."):
        m = SEGMENT.fullmatch(segment)
        if not m:
            raise LookupError(f"{location}: cannot read {segment!r}")
        name, bracket = m.groups()

        if not (isinstance(tp, type) and issubclass(tp, BaseModel)):
            raise LookupError(f"{location}: {name} is below a non-model")  # noqa: TRY004 -- the location is wrong, not a type
        if name not in tp.model_fields:
            raise LookupError(f"{location}: {tp.__name__} has no field {name!r}")

        # 後で定義されるモデル (RelationTarget, File など) の注釈は文字列のままなので、get_type_hints で解決する。
        tp = _unwrap_optional(get_type_hints(tp)[name])
        container = get_origin(tp)

        if bracket is None:
            if container in (list, dict):
                raise LookupError(f"{location}: {name} is a {container.__name__}")
        elif bracket.startswith("["):
            if container is not list:
                raise LookupError(f"{location}: {name} is not a list")
            tp = get_args(tp)[0]
        else:
            if container is not dict:
                raise LookupError(f"{location}: {name} is not a dict")
            tp = get_args(tp)[1]

    return tp


class _UniqueKeyLoader(yaml.SafeLoader):
    """同じ key が 2 度書かれていたら、後の方で黙って上書きせずに失敗する。"""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        keys = [self.construct_object(key, deep=deep) for key, _ in node.value]
        duplicates = {key for key in keys if keys.count(key) > 1}
        if duplicates:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate keys: {sorted(duplicates)}", node.start_mark
            )
        return super().construct_mapping(node, deep=deep)


def load_mapping(name: str) -> dict[str, dict[str, str]]:
    return yaml.load(  # type: ignore[no-any-return]
        FIXTURES_V3.joinpath("mapping", name).read_text(encoding="utf-8"),
        Loader=_UniqueKeyLoader,
    )


def load_record(name: str) -> Any:
    return json.loads(FIXTURES_V3.joinpath("records", name).read_text(encoding="utf-8"))


def rows(mapping: dict[str, dict[str, str]]) -> dict[str, str]:
    """対応表の行ごとの v3 の場所。値を持たない入れ物は除く。"""
    return {
        f"{part}:{item}": location
        for part, items in mapping.items()
        for item, location in items.items()
        if location != CONTAINER
    }


def _matches(item: Any, annotation: str) -> bool:
    """`[part_of sample]` や `[primary]` の注記に合う要素か。

    注記の語は順に、要素の type と、relation なら target.db に当たる。
    """
    words = annotation.split()
    if not words:
        return True
    if not isinstance(item, dict):
        return False

    actual = [item.get("type"), (item.get("target") or {}).get("db")]
    assert len(words) <= len(actual), f"cannot read the note [{annotation}]"

    return words == actual[: len(words)]


def values_at(data: Any, location: str) -> list[Any]:
    """location にある値を、list の注記に合う全ての要素にわたって集める。"""
    found = [data]

    for segment in strip_note(location).split("."):
        m = SEGMENT.fullmatch(segment)
        assert m, segment
        name, bracket = m.groups()

        found = [item[name] for item in found if isinstance(item, dict) and item.get(name) not in (None, "")]

        if bracket is not None and bracket.startswith("["):
            annotation = bracket[1:-1]
            found = [element for items in found for element in items if _matches(element, annotation)]
        elif bracket is not None:
            key = bracket[1:-1]
            found = [items[key] for items in found if key in items]

    return found
