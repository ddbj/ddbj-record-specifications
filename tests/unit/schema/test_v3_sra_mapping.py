"""tests/fixtures/v3/mapping/sra.yml の行が、v3 のモデルと実例に合っていることを確かめる。

対応表は SRA XML の要素と属性の 1 つ 1 つについて、v3 のどこに置くかを書いたもの。
行が正しい場所を指しているか (TAG を value に写していないか、など) は確かめない。
それは対応表を読む人が決める。ここで確かめるのは次のこと。

- 対応表が指す v3 の場所が、どれもモデルに実在する
- 属性と、要素の名前が値になるものは、値 (str / int / float / bool) の場所を指す
- raw fixture の SRA XML に出てくる要素と属性が、どれも対応表にある
- 対応表の全ての場所に、sra_full.json の中で値がある
"""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from .mapping_helpers import FIXTURES_V3, SCALARS, load_mapping, load_record, resolve, rows, values_at

RAW_DRA = FIXTURES_V3.joinpath("raw/dra")
SRA_FULL = load_record("sra_full.json")
MAPPING = load_mapping("sra.yml")


ROWS = rows(MAPPING)


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
    root = ET.parse(path).getroot()

    # *_SET は同じ種類の要素を並べるだけの入れ物で、record の中ではリストになる。
    entities = list(root) if root.tag.endswith("_SET") else [root]
    found = set().union(*(_paths(entity) for entity in entities))

    assert found - set(MAPPING[doc]) == set()


@pytest.mark.parametrize("location", sorted(set(ROWS.values())))
def test_the_full_record_has_a_value_at_every_location(location: str) -> None:
    # 対応表の全ての行が、少なくとも 1 つの実例で書けることを示す。
    assert values_at(SRA_FULL, location)
