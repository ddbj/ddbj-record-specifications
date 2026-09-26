"""docs/v3-gea-mapping.yml の行が、v3 のモデルと実例に合っていることを確かめる。

対応表は GEA のメタデータ (IDF / SDRF / ADF / CIBEX) の項目 1 つ 1 つについて、v3 のどこに置くかを
書いたもの。行が正しい場所を指しているかは確かめない。それは scripts/gea/build_mapping.py の規則と、
それを読む人が決める。ここで確かめるのは次のこと。

- 対応表が指す v3 の場所が、どれもモデルに実在し、ファイルのまま指すもの (ADF の表、表でない SDRF) を
  除いて値の場所である
- raw fixture の GEA のファイルに出てくる項目が、どれも対応表にある
- ファイルの読み方の規則 (scripts/gea/census_gea.py) が、それぞれの癖を持つ raw fixture で働く
- 対応表の全ての場所に、gea_*.json のどれかの中で値がある
"""

import json
from pathlib import Path
from typing import Any

import pytest

from .mapping_helpers import ROOT, SCALARS, load_mapping, load_record, load_script, resolve, rows, values_at

RAW_GEA = ROOT.joinpath("tests/fixtures/v3/raw/gea")
MAPPING = load_mapping("v3-gea-mapping.yml")
# 表として読めない SDRF は、表の行と同じ record には現れないので、別の record にした。
RECORDS = [load_record(name) for name in ("gea_full.json", "gea_array_design_full.json", "gea_unread_sdrf.json")]

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


# ファイルのまま指すもの: ADF の表と、表として読まない SDRF。
FILE_ROWS = {"adf:(table)", "sdrf:(unread)"}
VALUE_ROWS = {row: location for row, location in ROWS.items() if row not in FILE_ROWS}


@pytest.mark.parametrize("location", VALUE_ROWS.values(), ids=VALUE_ROWS.keys())
def test_every_item_but_the_files_lands_on_a_value(location: str) -> None:
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


def test_a_space_before_a_bracket_is_not_counted(tmp_path: Path) -> None:
    # E-GEAD-637 などの古い版の形: Comment [x]、Factor Value [x]、Unit [x]。
    sdrf = _write(
        tmp_path,
        "x.sdrf.txt",
        "Source Name\tComment [BioSample]\tAssay Name\tFactor Value [age]\tUnit [time unit]\ns1\tSAMD1\ta1\t5\tday\n",
    )

    assert set(_census(sdrf)["sdrf"]["items"]) == {
        "Source Name",
        "Comment[*] @ Source Name",
        "Assay Name",
        "Factor Value[*]",
        "Unit[*] @ Factor Value[*]",
    }


@pytest.mark.parametrize(
    ("text", "form"),
    [
        # CSV で保存された版 (E-GEAD-670、856)。
        ('"Source Name","Assay Name"\r\n"s1","a1"\r\n', "CSV"),
        # SDRF の代わりに IDF が保存された版 (E-GEAD-324、342)。
        ("Comment[GEAAccession]\tE-GEAD-1\t\t\nInvestigation Title\tx\nSDRF File\tE-GEAD-1.sdrf.txt\n", "IDF"),
    ],
)
def test_an_sdrf_in_a_known_other_form_is_left_unread(tmp_path: Path, text: str, form: str) -> None:
    census = _census(_write(tmp_path, "x.sdrf.txt", text))

    assert census["sdrf"]["unread"] == {"x.sdrf.txt": form}
    assert census["sdrf"]["items"] == {}
    assert _unrepresentable(census) == {}
    assert set(build_mapping.items(census)["sdrf"]) <= set(MAPPING["sdrf"])


@pytest.mark.parametrize(
    "text",
    [
        # 空白で区切ったもの。CSV でも IDF でもない。
        "Source Name Assay Name\ns1 a1\n",
        "# a comment\nSource Name\tAssay Name\ns1\ta1\n",
    ],
)
def test_an_sdrf_in_an_unknown_form_is_unrepresentable(tmp_path: Path, text: str) -> None:
    census = _census(_write(tmp_path, "x.sdrf.txt", text))

    assert census["sdrf"]["unread"] == {}
    assert _unrepresentable(census) == {
        "unrepresentable: SDRFs that neither start with Source Name nor are in a known form": 1
    }


@pytest.mark.parametrize(
    "text",
    [
        "\ufeffSource Name\tAssay Name\ns1\ta1\n",
        # 見出しの無い列が先頭にある。
        "\tSource Name\tAssay Name\n\ts1\ta1\n",
    ],
)
def test_a_table_starting_with_source_name_is_read(tmp_path: Path, text: str) -> None:
    census = _census(_write(tmp_path, "x.sdrf.txt", text))

    assert census["sdrf"]["unread"] == {}
    assert set(census["sdrf"]["items"]) == {"Source Name", "Assay Name"}


def test_a_heading_in_another_case_is_read_and_left_without_a_rule(tmp_path: Path) -> None:
    # MAGE-TAB の見出しは大文字小文字を区別しないが、保存された SDRF には無い。現れたら規則が無いとして
    # build_mapping.py が止まる (表でないとして黙って読まずに済ませない)。
    census = _census(_write(tmp_path, "x.sdrf.txt", "source name\tAssay Name\ns1\ta1\n"))

    assert census["sdrf"]["unread"] == {}
    assert [item for item in census["sdrf"]["items"] if build_mapping.sdrf_rule(item) is None] == ["source name @ None"]


@pytest.mark.parametrize("text", ["", "\n\t\n"])
def test_an_empty_sdrf_is_unrepresentable(tmp_path: Path, text: str) -> None:
    assert _unrepresentable(_census(_write(tmp_path, "x.sdrf.txt", text))) == {"unrepresentable: empty SDRFs": 1}


def test_an_empty_column_without_a_heading_is_left_out(tmp_path: Path) -> None:
    # E-GEAD-1066 の古い版の形: 見出しも値も無い列が、途中と末尾にある。
    sdrf = _write(tmp_path, "x.sdrf.txt", "Source Name\t\tAssay Name\t\ns1\t\ta1\t\t\n")

    census = _census(sdrf)

    assert set(census["sdrf"]["items"]) == {"Source Name", "Assay Name"}
    assert census["sdrf"]["items"]["Assay Name"]["kinds"] == {"str": ["a1"]}
    assert census["anomalies"] == {"SDRFs with an empty column without a heading": 1}


def test_a_row_short_of_its_last_factor_values_loses_nothing(tmp_path: Path) -> None:
    # 335 行の形: 末尾の Factor Value と Unit の欄が欠けている。
    sdrf = _write(
        tmp_path,
        "x.sdrf.txt",
        "Source Name\tAssay Name\tFactor Value[a]\tUnit[time unit]\ns1\ta1\t5\thour\ns2\ta2\n",
    )

    census = _census(sdrf)

    assert census["anomalies"] == {"rows whose width differs from the header": 1}
    # 欠けた欄は値として数えない (空の値と同じく、無いもの)。
    assert census["sdrf"]["items"]["Factor Value[*]"]["kinds"] == {"int": ["5"]}
    assert _unrepresentable(census) == {}


@pytest.mark.parametrize(
    "text",
    [
        # 見出しの無い列に値がある。
        "Source Name\t\tAssay Name\ns1\tlost\ta1\n",
        # 見出しより後に値がある。
        "Source Name\tAssay Name\ns1\ta1\tlost\n",
    ],
)
def test_a_value_without_a_heading_is_unrepresentable(tmp_path: Path, text: str) -> None:
    sdrf = _write(tmp_path, "x.sdrf.txt", text)

    assert _unrepresentable(_census(sdrf)) == {"unrepresentable: SDRF values in a column without a heading": 1}


def test_columns_after_a_data_file_other_than_comments_are_misplaced(tmp_path: Path) -> None:
    # E-GEAD-889 などの古い版の形。MAGE-TAB のデータファイルは Comment しか持たない。
    sdrf = _write(
        tmp_path,
        "x.sdrf.txt",
        "Source Name\tAssay Name\tDerived Array Data File\tComment[md5]\tFactor Value[t]\t"
        "Parameter Value[temperature]\tUnit[temperature unit]\tReplicate\tCharacteristics[genotype]\tTerm Source REF\n"
        "s1\ta1\tf.txt\t0123\t5\t28\tdegree Celsius\tbiological replicate-1\twild type\tEFO\n",
    )

    locations = {item: build_mapping.sdrf_rule(item) for item in _census(sdrf)["sdrf"]["items"]}

    assert locations["Comment[*] @ Derived Array Data File"].startswith("investigation.sdrf[].data_files[].comments[]")
    assert locations["Factor Value[*]"].startswith("investigation.sdrf[].factor_values[]")
    assert locations["Term Source REF @ Derived Array Data File"] is None
    for item in (
        "Characteristics[*] @ Derived Array Data File",
        "Parameter Value[*] @ Derived Array Data File",
        "Unit[*] @ Parameter Value[*] @ Derived Array Data File",
        "Replicate @ Derived Array Data File",
    ):
        assert locations[item].startswith("investigation.sdrf[].misplaced_columns[].value"), item


def test_misplaced_columns_of_one_name_are_one_list_for_the_row(tmp_path: Path) -> None:
    # misplaced_columns は行に 1 つの list なので、別のデータファイルの後の同じ名前の列でも、空の欄の後に
    # 値があれば値の位置がずれる。
    sdrf = _write(
        tmp_path,
        "x.sdrf.txt",
        "Source Name\tArray Data File\tReplicate\tDerived Array Data File\tReplicate\ns1\tf1\t\tf2\t2\n",
    )

    assert _unrepresentable(_census(sdrf)) == {
        "unrepresentable: SDRF rows with an empty cell before a value of the same column": 1
    }


def test_idf_tags(tmp_path: Path) -> None:
    idf = _write(
        tmp_path,
        "x.idf.txt",
        "Comment [GEAAccession]\tE-GEAD-1\nComment[AdditionalFile:txt]\tmap.txt\nComment[Public Release Date]\t2019-03-27\n",
    )

    tags = set(_census(idf)["idf"])

    assert tags == {"Comment[GEAAccession]", "Comment[AdditionalFile:txt]", "Comment[Public Release Date]"}
    assert build_mapping.idf_rule("Comment[AdditionalFile:txt]").startswith("investigation.additional_files[].name")
    assert build_mapping.idf_rule("Comment[Public Release Date]").startswith("submission.hold_date")


@pytest.mark.parametrize(
    ("text", "anomaly"),
    [
        (
            "Public Release Date\t2019-03-27\nComment[Public Release Date]\t2019-04-01\n",
            "unrepresentable: IDFs with both Public Release Date and Comment[Public Release Date]",
        ),
        ("Investigation Title\tx\n\tlost\n", "unrepresentable: IDF values on a line without a tag"),
        ("# a comment\nInvestigation Title\tx\n", "unrepresentable: IDF comment lines"),
    ],
)
def test_idf_lines_v3_cannot_hold(tmp_path: Path, text: str, anomaly: str) -> None:
    assert _unrepresentable(_census(_write(tmp_path, "x.idf.txt", text))) == {anomaly: 1}


def test_an_adf_header_tag_with_a_space_before_its_bracket(tmp_path: Path) -> None:
    adf = _write(
        tmp_path, "x.adf", "Comment [GEAAccession]\tA-GEAD-1\nArray Design Name\tx\n\n[main]\nReporter Name\nr1\n"
    )

    census = _census(adf)

    assert set(census["adf"]["header"]) == {"Comment[GEAAccession]", "Array Design Name"}
    assert census["adf"]["forms"] == {"MAGE-TAB ADF": 1}


@pytest.mark.parametrize(
    "text",
    [
        # 置き場所の無い Unit も、行に 1 つの list の要素。
        (
            "Source Name\tArray Data File\tParameter Value[t]\tUnit[time unit]\tDerived Array Data File\t"
            "Parameter Value[t]\tUnit[time unit]\ns1\tf1\t5\t\tf2\t6\thour\n"
        ),
        # factor_values も行に 1 つの list。
        "Source Name\tFactor Value[t]\tAssay Name\tFactor Value[t]\ns1\t\ta1\t5\n",
        "Source Name\tArray Data File\tFactor Value[t]\tDerived Array Data File\tFactor Value[t]\ns1\tf1\t\tf2\t5\n",
    ],
)
def test_lists_of_the_row_are_checked_across_the_row(tmp_path: Path, text: str) -> None:
    assert _unrepresentable(_census(_write(tmp_path, "x.sdrf.txt", text))) == {
        "unrepresentable: SDRF rows with an empty cell before a value of the same column": 1
    }


def test_a_node_in_another_case_after_a_data_file_has_no_rule(tmp_path: Path) -> None:
    sdrf = _write(
        tmp_path,
        "x.sdrf.txt",
        "Source Name\tArray Data File\tDerived array data file\ns1\tf1\tf2\n",
    )

    items = _census(sdrf)["sdrf"]["items"]

    assert build_mapping.sdrf_rule("Derived array data file @ Array Data File") is None
    assert "Derived array data file @ Array Data File" in items


def test_build_mapping_writes_nothing_while_anything_is_unrepresentable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    census = _census(_write(tmp_path, "x.sdrf.txt", "Source Name\t\tAssay Name\ns1\tlost\ta1\n"))
    census_path = _write(tmp_path, "census.json", json.dumps(census))
    out = tmp_path / "mapping.yml"
    monkeypatch.setattr("sys.argv", ["build_mapping.py", str(census_path), str(out)])

    with pytest.raises(SystemExit) as exit_info:
        build_mapping.main()

    assert exit_info.value.code == 1
    assert not out.exists()


def test_census_refuses_a_directory_the_export_did_not_finish(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dordb = tmp_path / "dordb"
    (dordb / "idf" / "E-GEAD-1").mkdir(parents=True)
    _write(dordb / "idf" / "E-GEAD-1", "E-GEAD-1_v1.idf.txt", "Investigation Title\tx\n")
    _write(dordb, "fingerprint.json", json.dumps({"written": {"idf": 2}}))
    monkeypatch.setattr("sys.argv", ["census_gea.py", str(dordb), str(tmp_path), str(tmp_path / "census.json")])

    with pytest.raises(SystemExit, match=r"does not hold what export_dordb\.rb wrote"):
        census_gea.main()


def test_an_alias_in_gea_accession_goes_to_alias() -> None:
    assert "investigation.alias" in build_mapping.idf_rule("Comment[GEAAccession]")
