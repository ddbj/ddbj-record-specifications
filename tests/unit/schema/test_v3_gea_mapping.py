"""docs/v3-gea-mapping.yml の行が、v3 のモデルと実例に合っていることを確かめる。

対応表は GEA のメタデータ (IDF / SDRF / ADF / CIBEX) の項目 1 つ 1 つについて、v3 のどこに置くかを
書いたもの。行が正しい場所を指しているかは確かめない。それは scripts/gea/build_mapping.py の規則と、
それを読む人が決める。ここで確かめるのは次のこと。

- 対応表が指す v3 の場所が、どれもモデルに実在し、ADF の表を除いて値の場所である
- raw fixture の GEA のファイルに出てくる項目が、どれも対応表にある
- ファイルの読み方の規則 (scripts/gea/census_gea.py) が、それぞれの癖を持つ raw fixture で働く
- 対応表の全ての場所に、gea_full.json か gea_array_design_full.json の中で値がある
"""

from pathlib import Path
from typing import Any

import pytest

from .mapping_helpers import ROOT, SCALARS, load_mapping, load_record, load_script, resolve, rows, values_at

RAW_GEA = ROOT.joinpath("tests/fixtures/v3/raw/gea")
MAPPING = load_mapping("v3-gea-mapping.yml")
RECORDS = [load_record("gea_full.json"), load_record("gea_array_design_full.json")]

census_gea = load_script("scripts/gea/census_gea.py")
build_mapping = load_script("scripts/gea/build_mapping.py")

ROWS = rows(MAPPING)


def _census(*paths: Path) -> dict[str, Any]:
    by_suffix = {
        suffix: sorted(p for p in paths if p.name.endswith(suffix))
        for suffix in (".idf.txt", ".sdrf.txt", ".adf", ".metadata")
    }
    return census_gea.census(*by_suffix.values())  # type: ignore[no-any-return]


def _raw(pattern: str) -> list[Path]:
    return sorted(RAW_GEA.glob(pattern))


@pytest.mark.parametrize("location", ROWS.values(), ids=ROWS.keys())
def test_every_location_exists_in_the_model(location: str) -> None:
    resolve(location)


VALUE_ROWS = {row: location for row, location in ROWS.items() if row != "adf:(table)"}


@pytest.mark.parametrize("location", VALUE_ROWS.values(), ids=VALUE_ROWS.keys())
def test_every_item_but_the_adf_table_lands_on_a_value(location: str) -> None:
    assert resolve(location) in SCALARS


def test_every_item_in_the_raw_files_is_mapped() -> None:
    census = _census(*_raw("*/*"))

    # 各部分にファイルが 1 つ以上あること。無ければ、下の確かめが何も確かめない。
    assert set(census["files"]) == {"idf", "sdrf", "adf", "cibex"}

    for part, items in build_mapping.items(census).items():
        assert set(items) - set(MAPPING[part]) == set(), part


def test_nothing_in_the_raw_files_is_unrepresentable() -> None:
    anomalies = _census(*_raw("*/*"))["anomalies"]

    assert {name: n for name, n in anomalies.items() if name.startswith("unrepresentable:")} == {}


def test_a_backslash_quote_does_not_end_an_idf_value() -> None:
    # E-GEAD-291 の Experiment Description は \\" で何重にも囲まれ、途中に改行がある。\\" で
    # 値が終わったと読むと、2 行目以降が IDF の項目の名前になってしまう。
    idf = _census(*_raw("E-GEAD-291/*.idf.txt"))["idf"]

    assert set(idf) <= set(MAPPING["idf"])
    assert idf["Experiment Description"]["max_repeat"] == 1


def test_a_unit_follows_its_factor_value() -> None:
    items = _census(*_raw("E-GEAD-284/*.sdrf.txt"))["sdrf"]["items"]

    assert "Unit[*] @ Factor Value[*]" in items


def test_adf_forms() -> None:
    forms = _census(*_raw("A-GEAD-*/*.adf"))["adf"]["forms"]

    assert forms == {"MAGE-TAB ADF": 1, "vendor table": 1, "dummy": 1}


@pytest.mark.parametrize(
    ("cibex", "section", "entries"),
    [
        # 列の説明の表の後に、見出しの無い hybridization が続く。それを表の行として読むと、
        # 4 つの hybridization のうち最初の 1 つしか残らない。
        ("CBX27", "Hybridization", 4),
        ("CBX62", "Summary", 2),
        # 表の後に何も続かないもの。
        ("CBX55", "Hybridization", 1),
    ],
)
def test_cibex_entries_after_a_table_of_fields_stay_entries(cibex: str, section: str, entries: int) -> None:
    blocks = _census(*_raw(f"{cibex}/*.metadata"))["cibex"]["blocks_per_file"]

    assert blocks[section] == {entries: 1}


def test_a_space_separated_reference_is_read_as_keys_and_values() -> None:
    census = _census(*_raw("CBX253/*.metadata"))

    assert census["anomalies"]["CIBEX lines separating a key from its value with spaces"] == 5
    assert {"Title", "Journal", "Year", "Volume"} <= set(census["cibex"]["sections"]["Reference"])


@pytest.mark.parametrize("location", sorted(set(ROWS.values())))
def test_the_full_records_have_a_value_at_every_location(location: str) -> None:
    # 対応表の全ての行が、少なくとも 1 つの実例で書けることを示す。
    assert any(values_at(record, location) for record in RECORDS)


# --- 読み方の規則を、仮のファイルで確かめる


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _unrepresentable(census: dict[str, Any]) -> dict[str, int]:
    return {name: n for name, n in census["anomalies"].items() if name.startswith("unrepresentable:")}


def test_an_empty_cell_before_a_value_of_the_same_column_is_unrepresentable(tmp_path: Path) -> None:
    sdrf = _write(
        tmp_path,
        "x.sdrf.txt",
        "Source Name\tProtocol REF\tProtocol REF\tExtract Name\tAssay Name\ns1\t\tP-2\te1\ta1\n",
    )

    assert _unrepresentable(_census(sdrf)) == {
        "unrepresentable: SDRF rows with an empty cell before a value of the same column": 1
    }


def test_a_unit_goes_with_its_own_factor_value(tmp_path: Path) -> None:
    # 2 つの Factor Value の Unit が同じ名前でも、それぞれの Factor Value のもの。
    sdrf = _write(
        tmp_path,
        "x.sdrf.txt",
        "Source Name\tAssay Name\tFactor Value[a]\tUnit[time unit]\tFactor Value[b]\tUnit[time unit]\n"
        "s1\ta1\t\t\t5\thour\n",
    )

    assert _unrepresentable(_census(sdrf)) == {}


def test_a_trailing_backslash_quote_in_an_sdrf_is_a_quote(tmp_path: Path) -> None:
    # E-GEAD-693 / 1075 の形: 引用符の外の値の末尾の \\"。
    sdrf = _write(tmp_path, "x.sdrf.txt", 'Source Name\tComment[provider]\ns1\tCLEA Japan, Inc.\\"\n')

    assert _census(sdrf)["sdrf"]["items"]["Comment[*] @ Source Name"]["kinds"]["str"] == ['CLEA Japan, Inc."']


def test_other_backslashes_are_kept() -> None:
    # ADF の表には D1Bda10\\2 のような値がある。
    assert census_gea.rows_of("D1Bda10\\2\tNOL1\\/NOP2\n") == [["D1Bda10\\2", "NOL1\\/NOP2"]]
    assert census_gea.rows_of("D1Bda10\\2\n", backslash_quotes=True) == [["D1Bda10\\2"]]


def test_an_adf_header_keeps_its_empty_cells_in_place(tmp_path: Path) -> None:
    # Term Source Name / File / Version は同じ位置どうしが組になる。
    adf = _write(
        tmp_path,
        "x.adf",
        "Comment[GEAAccession]\tA-GEAD-1\nTerm Source Name\ta\t\tc\n\n[main]\nReporter Name\nr1\n",
    )

    header = _census(adf)["adf"]["header"]

    assert header["Term Source Name"]["max_repeat"] == 3
    assert "empty" in header["Term Source Name"]["kinds"]


def test_a_table_split_by_a_blank_line_stays_a_table(tmp_path: Path) -> None:
    # CBX134 / CBX157 の形: 列の説明の表が空行で途切れる。
    cibex = _write(
        tmp_path,
        "x.metadata",
        "CIBEX accession\tCBX1\n\nHybridization:\nName\th1\nFile\tf1.txt\n\n"
        "Hybridization data text field:\nField\tDescription\nX\tx coordinate\n\nY\ty coordinate\n",
    )

    census = _census(cibex)

    assert census["cibex"]["blocks_per_file"]["Hybridization"] == {1: 1}
    assert _unrepresentable(census) == {}


def test_a_block_that_could_be_rows_or_an_entry_is_unrepresentable(tmp_path: Path) -> None:
    # 表に Description という名前の列があり、そこで空行が入ると、表の続きとも、Name の無い
    # hybridization とも読める。
    cibex = _write(
        tmp_path,
        "x.metadata",
        "CIBEX accession\tCBX1\n\nHybridization:\nName\th1\nFile\tf1.txt\n\n"
        "Hybridization data text field:\nField\tDescription\nX\tx coordinate\n\nDescription\tgene description\n",
    )

    assert _unrepresentable(_census(cibex)) == {
        "unrepresentable: CIBEX blocks that could be a table's rows or an entry": 1
    }
