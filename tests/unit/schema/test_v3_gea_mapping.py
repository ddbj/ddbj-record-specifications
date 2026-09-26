"""tests/fixtures/v3/mapping/gea.yml の行が、v3 のモデルと実例に合っていることを確かめる。

対応表は GEA のメタデータ (IDF / SDRF / ADF / CIBEX) の項目 1 つ 1 つについて、v3 のどこに置くかを
書いたもの。行が正しい場所を指しているかは確かめない。それは対応表を読む人が決める。
ここで確かめるのは次のこと。

- 対応表が指す v3 の場所が、どれもモデルに実在し、ADF の表を除いて値の場所である
- 対応表の全ての場所に、gea_full.json か gea_array_design_full.json の中で値がある
"""

import pytest

from .mapping_helpers import SCALARS, load_mapping, load_record, resolve, rows, values_at

MAPPING = load_mapping("gea.yml")
RECORDS = [load_record("gea_full.json"), load_record("gea_array_design_full.json")]

ROWS = rows(MAPPING)


@pytest.mark.parametrize("location", ROWS.values(), ids=ROWS.keys())
def test_every_location_exists_in_the_model(location: str) -> None:
    resolve(location)


VALUE_ROWS = {row: location for row, location in ROWS.items() if row != "adf:(table)"}


@pytest.mark.parametrize("location", VALUE_ROWS.values(), ids=VALUE_ROWS.keys())
def test_every_item_but_the_adf_table_lands_on_a_value(location: str) -> None:
    assert resolve(location) in SCALARS


@pytest.mark.parametrize("location", sorted(set(ROWS.values())))
def test_the_full_records_have_a_value_at_every_location(location: str) -> None:
    # 対応表の全ての行が、少なくとも 1 つの実例で書けることを示す。
    assert any(values_at(record, location) for record in RECORDS)
