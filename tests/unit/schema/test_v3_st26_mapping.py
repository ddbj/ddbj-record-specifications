"""tests/fixtures/v3/mapping/st26.yml の行が、v3 のモデルと DTD と実例に合っていることを確かめる。

対応表は ST.26 の配列表の項目 1 つ 1 つについて、v3 のどこに置くかを書いたもの。ヘッダー (header) と
SequenceData の中 (sequences) に分かれている。行が正しい場所を指しているかは確かめない。それは対応表を
読む人が決める。ここで確かめるのは次のこと。

- 対応表が指す v3 の場所が、どれもモデルに実在し、ヘッダーの SequenceData を除いて値の場所である
- WIPO の DTD が宣言する要素と属性が、どれも対応表の該当する節にある
- raw fixture の ST.26 のファイルに出てくる要素と属性が、どれも対応表の該当する節にある
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
def test_every_item_but_the_sequence_data_row_lands_on_a_value(location: str) -> None:
    assert resolve(location) in SCALARS


SEQUENCE_DATA = "ST26SequenceListing/SequenceData"


def _split(items: set[str]) -> dict[str, set[str]]:
    """項目を、ヘッダーと SequenceData の中に分ける。SequenceData そのものはヘッダーの側。"""
    inside = {item for item in items if item.startswith(f"{SEQUENCE_DATA}/")}
    return {"header": items - inside, "sequences": inside}


def _dtd_items(dtd: Path) -> dict[str, set[str]]:
    """DTD が宣言する、ルート要素の下の全ての要素と属性。"""
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
        found.update(f"{path}/@{attribute}" for attribute in attributes.get(element, []))
        for child in re.findall(r"[A-Za-z][\w-]*", models[element].replace("#PCDATA", "")):
            walk(child, f"{path}/{child}")

    for child in re.findall(r"[A-Za-z][\w-]*", models[root]):
        walk(child, f"{root}/{child}")

    return _split(found)


DTD_ITEMS = _dtd_items(RAW_ST26 / "ST26SequenceListing_V1_3.dtd")


@pytest.mark.parametrize("part", ["header", "sequences"])
def test_every_item_the_wipo_dtd_declares_is_mapped(part: str) -> None:
    assert DTD_ITEMS[part] - set(MAPPING[part]) == set()


def test_the_dtd_is_read() -> None:
    # DTD を読めていること。読めなければ、上の確かめが何も確かめない。
    assert {
        "ST26SequenceListing/@dtdVersion",
        "ST26SequenceListing/ApplicantName/@languageCode",
        "ST26SequenceListing/ApplicationIdentification/FilingDate",
    } <= DTD_ITEMS["header"]
    assert {
        f"{SEQUENCE_DATA}/@sequenceIDNumber",
        f"{SEQUENCE_DATA}/INSDSeq/INSDSeq_feature-table/INSDFeature/INSDFeature_quals/INSDQualifier/@id",
        f"{SEQUENCE_DATA}/INSDSeq/INSDSeq_feature-table/INSDFeature/INSDFeature_quals/INSDQualifier/NonEnglishQualifier_value",
    } <= DTD_ITEMS["sequences"]


def _raw_items(path: Path) -> dict[str, set[str]]:
    root = ET.parse(path).getroot()
    found = {f"{root.tag}/@{name}" for name in root.attrib}

    def walk(element: ET.Element, prefix: str) -> None:
        item = f"{prefix}/{element.tag}"
        found.add(item)
        found.update(f"{item}/@{name}" for name in element.attrib)
        for child in element:
            walk(child, item)

    for child in root:
        walk(child, root.tag)

    return _split(found)


RAW_FILES = sorted(RAW_ST26.glob("*.xml"))


@pytest.mark.parametrize("part", ["header", "sequences"])
@pytest.mark.parametrize("path", RAW_FILES, ids=lambda path: path.name)
def test_every_item_in_the_raw_files_is_mapped(path: Path, part: str) -> None:
    assert _raw_items(path)[part] - set(MAPPING[part]) == set()


# 対応表の key の `[000]` / `[source]` / `[organism]` などは、同じ要素の中を分けるための注記。
ANNOTATION = re.compile(r"\[[^\]]*\]")


@pytest.mark.parametrize("part", ["header", "sequences"])
def test_every_mapped_item_exists_in_the_dtd_or_the_raw_files(part: str) -> None:
    # 逆向きの確かめ。これが無いと、綴りを誤った key の行があっても上の確かめは通る。
    known = DTD_ITEMS[part].union(*(_raw_items(path)[part] for path in RAW_FILES))
    assert {ANNOTATION.sub("", item) for item in MAPPING[part]} - known == set()


def test_the_raw_files_include_the_jpo_bibliography() -> None:
    # JPO が足す Bibliography を持つファイルがあること。無ければ、上の確かめがそれを確かめない。
    assert "ST26SequenceListing/Bibliography/PublishedDate" in _raw_items(RAW_ST26 / "JPO-bibliography.xml")["header"]


@pytest.mark.parametrize("location", sorted(set(VALUE_ROWS.values())))
def test_the_full_record_has_a_value_at_every_location(location: str) -> None:
    # 対応表の全ての行が書けることを示す。
    assert values_at(ST26_FULL, location)
