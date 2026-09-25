"""docs/v3-sra-mapping.yml の行が、v3 のモデルと実例に合っていることを確かめる。

対応表は SRA XML の要素と属性の 1 つ 1 つについて、v3 のどこに置くかを書いたもの。
行が正しい場所を指しているか (TAG を value に写していないか、など) は確かめない。
それは scripts/sra/build_mapping.py の規則と、それを読む人が決める。ここで確かめるのは次のこと。

- 対応表が指す v3 の場所が、どれもモデルに実在する
- 属性と、要素の名前が値になるものは、値 (str / int / float / bool) の場所を指す
- raw fixture の SRA XML に出てくる要素と属性が、どれも対応表にある
- 対応表の全ての場所に、sra_full.json の中で値がある
"""

import importlib.util
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
RAW_DRA = ROOT.joinpath("tests/fixtures/v3/raw/dra")
SRA_FULL = json.loads(ROOT.joinpath("tests/fixtures/v3/records/sra_full.json").read_text(encoding="utf-8"))

# 対応表を書くスクリプトの読み方 (場所の書き方と、場所から型への解決) をそのまま使う。
_spec = importlib.util.spec_from_file_location("build_mapping", ROOT.joinpath("scripts/sra/build_mapping.py"))
assert _spec is not None
assert _spec.loader is not None
build_mapping = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_mapping)

CONTAINER = build_mapping.CONTAINER
SEGMENT = build_mapping.SEGMENT
resolve = build_mapping.resolve
strip_note = build_mapping.strip_note
SCALARS = (str, int, float, bool)


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


MAPPING: dict[str, dict[str, str]] = yaml.load(
    ROOT.joinpath("docs/v3-sra-mapping.yml").read_text(encoding="utf-8"),
    Loader=_UniqueKeyLoader,  # noqa: S506 -- a SafeLoader subclass
)


# 対応表の行ごとの v3 の場所。値を持たない入れ物は除く。
ROWS = {
    f"{doc}:{path}": location
    for doc, paths in MAPPING.items()
    for path, location in paths.items()
    if location != CONTAINER
}


@pytest.mark.parametrize("location", ROWS.values(), ids=ROWS.keys())
def test_every_location_exists_in_the_model(location: str) -> None:
    resolve(location)


VALUE_ROWS = {row: location for row, location in ROWS.items() if "/@" in row or "(要素名" in location}


@pytest.mark.parametrize("location", VALUE_ROWS.values(), ids=VALUE_ROWS.keys())
def test_attributes_and_element_names_land_on_a_value(location: str) -> None:
    assert resolve(location) in SCALARS


def _paths(element: ET.Element, prefix: str = "") -> set[str]:
    path = f"{prefix}/{element.tag}" if prefix else element.tag
    found = {path, *(f"{path}/@{name}" for name in element.attrib)}

    for child in element:
        found |= _paths(child, path)

    return found


def _documents() -> list[tuple[str, Path]]:
    return [(path.name.split(".")[-2], path) for path in sorted(RAW_DRA.glob("*/*.xml"))]


@pytest.mark.parametrize(("doc", "path"), _documents(), ids=lambda v: v.name if isinstance(v, Path) else v)
def test_every_path_in_raw_sra_xml_is_mapped(doc: str, path: Path) -> None:
    root = ET.parse(path).getroot()  # noqa: S314 -- fixture in this repository

    # *_SET は同じ種類の要素を並べるだけの入れ物で、record の中ではリストになる。
    entities = list(root) if root.tag.endswith("_SET") else [root]
    found = set().union(*(_paths(entity) for entity in entities))

    assert found - set(MAPPING[doc]) == set()


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


def _values_at(data: Any, location: str) -> list[Any]:
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


@pytest.mark.parametrize("location", sorted(set(ROWS.values())))
def test_the_full_record_has_a_value_at_every_location(location: str) -> None:
    # 対応表の全ての行が、少なくとも 1 つの実例で書けることを示す。
    assert _values_at(SRA_FULL, location)
