"""tests/fixtures/v3/mapping/gea.yml の行が、v3 のモデルと実例に合っていることを確かめる。

対応表は GEA のメタデータ (IDF / SDRF / ADF / CIBEX) の項目 1 つ 1 つについて、v3 のどこに置くかを
書いたもの。行が正しい場所を指しているかは確かめない。それは対応表を読む人が決める。
ここで確かめるのは次のこと。

- 対応表が指す v3 の場所が、どれもモデルに実在し、ファイルのまま指すもの (ADF の表、表でない SDRF) を
  除いて値の場所である
- 対応表の全ての場所に、gea_*.json のどれかの中で値がある
"""

import pytest

from .mapping_helpers import SCALARS, load_mapping, load_record, resolve, rows, values_at

MAPPING = load_mapping("gea.yml")
# 表でない SDRF は、SDRF から作るオブジェクトと同じ record には現れないので、別の record にした。accession を
# 振る前の版 (IDF の Comment[GEAAccession] が alias) の形でもある。
RECORDS = [load_record(name) for name in ("gea_full.json", "gea_array_design_full.json", "gea_unread_sdrf.json")]

ROWS = rows(MAPPING)


@pytest.mark.parametrize("location", ROWS.values(), ids=ROWS.keys())
def test_every_location_exists_in_the_model(location: str) -> None:
    resolve(location)


# ファイルのまま指すもの。
FILE_ROWS = {"adf:(table)", "sdrf:(unread)"}
VALUE_ROWS = {row: location for row, location in ROWS.items() if row not in FILE_ROWS}


@pytest.mark.parametrize("location", VALUE_ROWS.values(), ids=VALUE_ROWS.keys())
def test_every_item_but_the_files_lands_on_a_value(location: str) -> None:
    assert resolve(location) in SCALARS


@pytest.mark.parametrize("location", sorted(set(ROWS.values())))
def test_the_full_records_have_a_value_at_every_location(location: str) -> None:
    # 対応表の全ての行が、少なくとも 1 つの実例で書けることを示す。
    assert any(values_at(record, location) for record in RECORDS)


def test_an_alias_in_gea_accession_has_a_place() -> None:
    # accession を振る前の版の Comment[GEAAccession] は alias。対応表の行では注記の中にあるので、
    # 上の確かめが見ない。ここで確かめる。
    assert "projects[].alias" in MAPPING["idf"]["Comment[GEAAccession]"]
    assert resolve("projects[].alias") in SCALARS
    assert any(values_at(record, "projects[].alias") for record in RECORDS)
