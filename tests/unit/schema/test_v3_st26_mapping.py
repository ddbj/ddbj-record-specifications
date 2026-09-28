"""tests/fixtures/v3/mapping/st26.yml の行が、v3 のモデルと DTD と実例に合っていることを確かめる。

対応表は ST.26 の配列表のヘッダー (SequenceData の外) の項目 1 つ 1 つについて、v3 のどこに置くかを
書いたもの。行が正しい場所を指しているかは確かめない。それは対応表を読む人が決める。
ここで確かめるのは次のこと。

- 対応表が指す v3 の場所が、どれもモデルに実在し、SequenceData を除いて値の場所である
- WIPO の DTD が宣言するヘッダーの要素と属性が、どれも対応表にある
- raw fixture の ST.26 のファイルのヘッダーに出てくる要素と属性が、どれも対応表にある
- 対応表の全ての場所に、st26_full.json の中で値がある
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from .mapping_helpers import FIXTURES_V3, SCALARS, load_mapping, load_record, resolve, rows, values_at

RAW_ST26 = FIXTURES_V3.joinpath("raw/st26")
ST26_FULL = load_record("st26_full.json")
MAPPING = load_mapping("st26.yml")

ROWS = rows(MAPPING)


@pytest.mark.parametrize("location", ROWS.values(), ids=ROWS.keys())
def test_every_location_exists_in_the_model(location: str) -> None:
    resolve(location)


VALUE_ROWS = {row: location for row, location in ROWS.items() if row != "header:ST26SequenceListing/SequenceData"}


@pytest.mark.parametrize("location", VALUE_ROWS.values(), ids=VALUE_ROWS.keys())
def test_every_item_but_the_sequences_lands_on_a_value(location: str) -> None:
    assert resolve(location) in SCALARS


def _dtd_header_items(dtd: Path) -> set[str]:
    """DTD が宣言する、ルート要素から SequenceData の手前までの要素と属性。"""
    text = re.sub(r"<!--.*?-->", "", dtd.read_text(encoding="utf-8"), flags=re.DOTALL)
    models = dict(re.findall(r"<!ELEMENT\s+(\S+)\s+(.*?)>", text, flags=re.DOTALL))
    attributes = {
        name: re.findall(r"(\w+)\s+(?:CDATA|ID|IDREF|NMTOKEN|\()", body)
        for name, body in re.findall(r"<!ATTLIST\s+(\S+)(.*?)>", text, flags=re.DOTALL)
    }

    root = "ST26SequenceListing"
    found = {f"{root}/@{attribute}" for attribute in attributes.get(root, [])}

    def walk(element: str, path: str) -> None:
        found.add(path)
        if element == "SequenceData":  # 属性も含めて、配列の側
            return
        found.update(f"{path}/@{attribute}" for attribute in attributes.get(element, []))
        for child in re.findall(r"[A-Za-z][\w-]*", models[element].replace("#PCDATA", "")):
            walk(child, f"{path}/{child}")

    for child in re.findall(r"[A-Za-z][\w-]*", models[root]):
        walk(child, f"{root}/{child}")

    return found


def test_every_header_item_the_wipo_dtd_declares_is_mapped() -> None:
    items = _dtd_header_items(RAW_ST26 / "ST26SequenceListing_V1_3.dtd")

    # DTD を読めていること。読めなければ、下の確かめが何も確かめない。
    assert {
        "ST26SequenceListing/@dtdVersion",
        "ST26SequenceListing/ApplicantName/@languageCode",
        "ST26SequenceListing/ApplicationIdentification/FilingDate",
    } <= items

    assert items - set(MAPPING["header"]) == set()


def _header_items(path: Path) -> set[str]:
    root = ET.parse(path).getroot()
    found = {f"{root.tag}/@{name}" for name in root.attrib}

    def walk(element: ET.Element, prefix: str) -> None:
        item = f"{prefix}/{element.tag}"
        found.add(item)
        if element.tag == "SequenceData":
            return
        found.update(f"{item}/@{name}" for name in element.attrib)
        for child in element:
            walk(child, item)

    for child in root:
        walk(child, root.tag)

    return found


@pytest.mark.parametrize("path", sorted(RAW_ST26.glob("*.xml")), ids=lambda path: path.name)
def test_every_header_item_in_the_raw_files_is_mapped(path: Path) -> None:
    assert _header_items(path) - set(MAPPING["header"]) == set()


def test_the_raw_files_include_the_jpo_bibliography() -> None:
    # JPO が足す Bibliography を持つファイルがあること。無ければ、上の確かめがそれを確かめない。
    assert "ST26SequenceListing/Bibliography/PublishedDate" in _header_items(RAW_ST26 / "JPO-bibliography.xml")


@pytest.mark.parametrize("location", sorted(set(VALUE_ROWS.values())))
def test_the_full_record_has_a_value_at_every_location(location: str) -> None:
    # 対応表の全ての行が書けることを示す。配列 (SequenceData) の中はこの表の外なので、
    # st26_full.json は sequences を持たない。
    assert values_at(ST26_FULL, location)
