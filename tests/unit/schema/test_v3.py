import json
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from ddbj_record.schema.v3 import (
    Attribute,
    DdbjRecord,
    LocusTagPrefix,
    Organism,
    Project,
    ProjectTarget,
    RelationSource,
    RelationTarget,
    Sample,
)

RECORDS_DIR = Path(__file__).resolve().parents[2].joinpath("fixtures", "v3", "records")


def _record_paths() -> list[Path]:
    return sorted(RECORDS_DIR.glob("*.json"))


# === fixture parsing ===
# 全 fixture がモデルを通ること。スキーマを変えて fixture を直し忘れる（あるいはその逆）を
# 落とすための土台で、個別の性質はこの下で確かめる。


@pytest.mark.parametrize("path", _record_paths(), ids=lambda p: p.stem)
def test_v3_record_fixture_parses(path: Path) -> None:
    with path.open("r", encoding="utf-8") as f:
        record = DdbjRecord.model_validate(json.load(f))
    assert record.schema_version == "v3"


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
        "schema_version": "v3",
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


def test_sample_keeps_its_named_attributes() -> None:
    sample = Sample.model_validate({"attributes": [{"name": "depth", "value": "10", "unit": "m"}]})

    assert sample.attributes is not None
    assert sample.attributes[0].unit == "m"


# === locus_tag_prefix ===


def test_locus_tag_prefix_carries_the_biosample_it_was_declared_with() -> None:
    project = Project.model_validate({"locus_tag_prefix": [{"prefix": "HSM01", "biosample_id": "SAMD00123456"}]})
    assert project.locus_tag_prefix is not None
    assert project.locus_tag_prefix[0].biosample_id == "SAMD00123456"


def test_locus_tag_prefix_biosample_id_is_optional() -> None:
    # Trad は prefix と対になる BioSample を持たない。
    prefix = LocusTagPrefix.model_validate({"prefix": "ECK12"})
    assert prefix.biosample_id is None


def test_locus_tag_prefix_rejects_a_bare_string() -> None:
    # v3 の途中まで list[str] だったので、古い形が黙って通らないことを固定しておく。
    with pytest.raises(ValidationError):
        Project.model_validate({"locus_tag_prefix": ["ECK12"]})


# === "other" の説明 ===


def test_target_carries_the_description_for_other_choices() -> None:
    target = ProjectTarget.model_validate(
        {
            "sample_scope": "eOther",
            "description": "Environmental mat communities.",
            "method": "eOther",
            "method_description": "In-house enrichment.",
            "data_types": ["eOther"],
            "data_type_descriptions": {"eOther": "Community composition tables."},
        }
    )
    assert target.description is not None
    assert target.method_description is not None
    assert target.data_type_descriptions == {"eOther": "Community composition tables."}


def test_umbrella_subtype_carries_its_description() -> None:
    project = Project.model_validate(
        {
            "project_type": "umbrella",
            "umbrella_subtype": "eOther",
            "umbrella_subtype_description": "A programme-level grouping.",
        }
    )
    assert project.umbrella_subtype_description == "A programme-level grouping."


# === organism.taxonomy_id ===
#
# 元の形式 (XML / TSV) では文字列で、登録者は前ゼロ・空・"not applicable" も書く。
# それを指摘するのはルールなので、型は書かれたままの文字列を持つ。


@pytest.mark.parametrize("value", ["9606", "009606", "", "not applicable", " 9606 "])
def test_organism_taxonomy_id_as_written_is_kept(value: str) -> None:
    assert Organism.model_validate({"taxonomy_id": value}).taxonomy_id == value


@given(st.integers())
def test_organism_taxonomy_id_as_a_number_is_rejected(value: int) -> None:
    with pytest.raises(ValidationError):
        Organism.model_validate({"taxonomy_id": value})


# === relations の index ===
#
# accession が無く alias も重なるオブジェクトは、その種類の list の中の位置 (0 始まり) で指す。
# 起点 (RelationSource) と相手 (RelationTarget、pool.members[].sample) で同じ規則にする。


@given(st.integers(min_value=0))
def test_relation_index_non_negative_is_accepted(index: int) -> None:
    assert RelationSource.model_validate({"type": "sample", "index": index}).index == index
    assert RelationTarget.model_validate({"db": "sample", "index": index}).index == index


@given(st.integers(max_value=-1))
def test_relation_source_index_negative_is_rejected(index: int) -> None:
    with pytest.raises(ValidationError):
        RelationSource.model_validate({"type": "sample", "index": index})


@given(st.integers(max_value=-1))
def test_relation_target_index_negative_is_rejected(index: int) -> None:
    with pytest.raises(ValidationError):
        RelationTarget.model_validate({"db": "sample", "index": index})


def test_pool_member_sample_with_index_points_among_samples_sharing_an_alias() -> None:
    # GEA の SDRF には、名前が同じで値の違う Source がある。別の sample にし、位置で指す。
    record = DdbjRecord.model_validate(
        {
            "schema_version": "v3",
            "samples": [
                {"alias": "PDAC3", "attributes": [{"name": "sample_name", "value": "PDAC3_Scr"}]},
                {"alias": "PDAC3", "attributes": [{"name": "sample_name", "value": "PDAC3_MNX1KD"}]},
            ],
            "experiments": [
                {"alias": "a1", "pool": {"members": [{"sample": {"db": "sample", "id": "PDAC3", "index": 1}}]}},
            ],
        }
    )

    assert record.experiments is not None
    assert record.experiments[0].pool is not None
    assert record.experiments[0].pool.members is not None
    sample = record.experiments[0].pool.members[0].sample
    assert sample is not None
    assert sample.index == 1


def test_pool_member_sample_with_negative_index_fails_the_whole_record() -> None:
    record = {
        "schema_version": "v3",
        "experiments": [{"pool": {"members": [{"sample": {"db": "sample", "id": "PDAC3", "index": -1}}]}}],
    }

    with pytest.raises(ValidationError) as excinfo:
        DdbjRecord.model_validate(record)

    locations = [error["loc"] for error in excinfo.value.errors()]

    assert ("experiments", 0, "pool", "members", 0, "sample", "index") in locations


# === projects ===
#
# SRA の STUDY_SET も BioProject XML も project を繰り返せる。1 つの submission を 1 つの record のまま
# 持てるように list にし、いくつまで許すかは ddbj-validator のルールで決める。


def test_projects_keep_every_study_of_a_submission_in_order() -> None:
    record = DdbjRecord.model_validate(
        {
            "schema_version": "v3",
            "submission": {"accession": "SRA002148"},
            "projects": [{"accession": "SRP000285"}, {"accession": "SRP019355"}],
        }
    )

    assert record.projects is not None
    assert [project.accession for project in record.projects] == ["SRP000285", "SRP019355"]


def test_projects_given_as_a_single_object_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DdbjRecord.model_validate({"schema_version": "v3", "projects": {"accession": "PRJDB1"}})


# === extra="forbid" ===


def test_project_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Project.model_validate({"title": "x", "bogus": 1})


def test_bioproject_other_fixture_is_fully_populated(v3_bioproject_other: dict[str, Any]) -> None:
    # BP の "other" 系ルールが要求する説明が一通り載っている fixture であること。
    record = DdbjRecord.model_validate(v3_bioproject_other)
    assert record.projects is not None
    project = record.projects[0]
    target = project.target
    assert target is not None
    assert target.description
    assert target.method_description
    assert target.data_type_descriptions
    assert project.locus_tag_prefix is not None
    assert project.locus_tag_prefix[0].biosample_id
