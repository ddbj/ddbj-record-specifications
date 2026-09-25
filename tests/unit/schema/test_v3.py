import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ddbj_record.schema.v3 import Attribute, DdbjRecord, Sample

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "v3" / "records"


# === Attribute.name ===
#
# 名前の無い属性は何の値かが分からず、検証も表示もしようがない。
# 正規化は前後の空白を落とすので、空白だけの名前も同じ扱いにする。


def test_attribute_with_a_name_is_valid() -> None:
    attribute = Attribute.model_validate({"name": "collection_date", "value": "2025-01-01"})

    assert attribute.name == "collection_date"


def test_attribute_name_is_required() -> None:
    with pytest.raises(ValidationError):
        Attribute.model_validate({"value": "2025-01-01"})


@pytest.mark.parametrize("name", ["", " ", "\t", "  \n "])
def test_attribute_name_must_not_be_blank(name: str) -> None:
    with pytest.raises(ValidationError):
        Attribute.model_validate({"name": name, "value": "2025-01-01"})


def test_a_name_with_surrounding_spaces_is_still_a_name() -> None:
    # 前後の空白は正規化で落ちるが、名前そのものは残る。拒否する理由は無い。
    assert Attribute.model_validate({"name": " depth ", "value": "10"}).name == " depth "


def test_a_nameless_attribute_fails_the_whole_record() -> None:
    record = {
        "schema_version": "v3.0",
        "samples": [{"alias": "s1", "attributes": [{"value": "10 m"}]}],
    }

    with pytest.raises(ValidationError) as excinfo:
        DdbjRecord.model_validate(record)

    locations = [error["loc"] for error in excinfo.value.errors()]

    assert ("samples", 0, "attributes", 0, "name") in locations


def test_the_json_schema_requires_the_name() -> None:
    schema = Attribute.model_json_schema()

    assert "name" in schema["required"]
    assert schema["properties"]["name"]["pattern"] == r"\S"


# === fixtures still parse ===


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.json")), ids=lambda p: p.name)
def test_v3_fixtures_parse(path: Path) -> None:
    DdbjRecord.model_validate(json.loads(path.read_text()))


def test_sample_keeps_its_named_attributes() -> None:
    sample = Sample.model_validate({"attributes": [{"name": "depth", "value": "10", "unit": "m"}]})

    assert sample.attributes is not None
    assert sample.attributes[0].unit == "m"
