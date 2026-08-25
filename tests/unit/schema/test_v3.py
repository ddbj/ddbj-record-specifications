import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from ddbj_record.schema.v3 import DdbjRecord, LocusTagPrefix, Project, ProjectTarget

RECORDS_DIR = (
    Path(__file__).resolve().parents[2].joinpath("fixtures", "v3", "records")
)


def _record_paths() -> list[Path]:
    return sorted(RECORDS_DIR.glob("*.json"))


# === fixture parsing ===
# 全 fixture がモデルを通ること。スキーマを変えて fixture を直し忘れる（あるいはその逆）を
# 落とすための土台で、個別の性質はこの下で確かめる。


@pytest.mark.parametrize("path", _record_paths(), ids=lambda p: p.stem)
def test_v3_record_fixture_parses(path: Path) -> None:
    with path.open("r", encoding="utf-8") as f:
        record = DdbjRecord.model_validate(json.load(f))
    assert record.schema_version == "v3.0"


# === locus_tag_prefix ===


def test_locus_tag_prefix_carries_the_biosample_it_was_declared_with() -> None:
    project = Project.model_validate(
        {
            "locus_tag_prefix": [
                {"prefix": "HSM01", "biosample_id": "SAMD00123456"}
            ]
        }
    )
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
    assert target.data_type_descriptions == {
        "eOther": "Community composition tables."
    }


def test_umbrella_subtype_carries_its_description() -> None:
    project = Project.model_validate(
        {
            "project_type": "umbrella",
            "umbrella_subtype": "eOther",
            "umbrella_subtype_description": "A programme-level grouping.",
        }
    )
    assert project.umbrella_subtype_description == "A programme-level grouping."


# === extra="forbid" ===


def test_project_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Project.model_validate({"title": "x", "bogus": 1})


def test_bioproject_other_fixture_is_fully_populated(
    v3_bioproject_other: dict[str, Any]
) -> None:
    # BP の "other" 系ルールが要求する説明が一通り載っている fixture であること。
    record = DdbjRecord.model_validate(v3_bioproject_other)
    assert record.project is not None
    target = record.project.target
    assert target is not None
    assert target.description
    assert target.method_description
    assert target.data_type_descriptions
    assert record.project.locus_tag_prefix is not None
    assert record.project.locus_tag_prefix[0].biosample_id
