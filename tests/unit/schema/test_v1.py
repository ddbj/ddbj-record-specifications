from typing import Any

import pytest
from pydantic import ValidationError

from ddbj_record.schema.v1 import (
    Common,
    CommonMeta,
    CommonSource,
    DdbjRecord,
    Entry,
    Feature,
    StComment,
    Submitter,
)
from ddbj_record.validator import validate_json_data

# === valid fixture parsing ===


def test_v1_valid_minimal_parses(v1_valid_minimal: dict[str, Any]) -> None:
    record = DdbjRecord.model_validate(v1_valid_minimal)
    assert record.schema_version == "v1.0"


def test_v1_valid_dfc_gnm_parses(v1_valid_dfc_gnm: dict[str, Any]) -> None:
    record = DdbjRecord.model_validate(v1_valid_dfc_gnm)
    assert len(record.ENTRIES) > 0


def test_v1_valid_wf_dfc_wgs_parses(v1_valid_wf_dfc_wgs: dict[str, Any]) -> None:
    record = DdbjRecord.model_validate(v1_valid_wf_dfc_wgs)
    assert record.COMMON.trad_submission_category in ("WGS", "GNM")


# === invalid fixture detection ===


def test_v1_invalid_missing_required_raises(v1_invalid_missing_required: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        DdbjRecord.model_validate(v1_invalid_missing_required)


def test_v1_invalid_wrong_type_raises(v1_invalid_wrong_type: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        DdbjRecord.model_validate(v1_invalid_wrong_type)


# === legacy schema_version normalization (via validate_json_data) ===


def test_v1_legacy_schema_version_normalized(v1_legacy_schema_version: dict[str, Any]) -> None:
    result = validate_json_data(v1_legacy_schema_version, "v1")
    assert result.valid is True
    assert v1_legacy_schema_version["schema_version"] == "v1.0"


def test_v1_schema_version_01_normalized() -> None:
    data = {
        "schema_version": "0.1",
        "COMMON": {
            "SUBMITTER": {
                "ab_name": ["Test,T."],
                "contact": "Test User",
                "email": "test@example.com",
                "institute": "Test Inst",
                "country": "Japan",
                "city": "Tokyo",
                "street": "1-1",
                "zip": "000-0000",
            },
            "ST_COMMENT": {
                "tagset_id": "Genome-Assembly-Data",
                "Assembly Method": "test v. 1",
                "Sequencing Technology": "Illumina",
            },
            "trad_submission_category": "GNM",
        },
        "COMMON_SOURCE": {"organism": "Test organism", "mol_type": "genomic DNA"},
        "COMMON_META": {"division": "BCT"},
    }
    result = validate_json_data(data, "v1")
    assert result.valid is True
    assert data["schema_version"] == "v1.0"


def test_v1_schema_version_v1_normalized() -> None:
    data = {
        "schema_version": "v1",
        "COMMON": {
            "SUBMITTER": {
                "ab_name": ["Test,T."],
                "contact": "Test User",
                "email": "test@example.com",
                "institute": "Test Inst",
                "country": "Japan",
                "city": "Tokyo",
                "street": "1-1",
                "zip": "000-0000",
            },
            "ST_COMMENT": {
                "tagset_id": "Genome-Assembly-Data",
                "Assembly Method": "test v. 1",
                "Sequencing Technology": "Illumina",
            },
            "trad_submission_category": "GNM",
        },
        "COMMON_SOURCE": {"organism": "Test organism", "mol_type": "genomic DNA"},
        "COMMON_META": {"division": "BCT"},
    }
    result = validate_json_data(data, "v1")
    assert result.valid is True
    assert data["schema_version"] == "v1.0"


# === Literal type boundary values ===


@pytest.mark.parametrize("entry_type", ["chromosome", "plasmid", "unplaced", "other"])
def test_v1_entry_type_valid_values(entry_type: str) -> None:
    entry = Entry(
        id="test",
        name="test",
        type=entry_type,
        topology="linear",
        sequence=None,
    )
    assert entry.type == entry_type


def test_v1_entry_type_invalid_value_raises() -> None:
    with pytest.raises(ValidationError):
        Entry(
            id="test",
            name="test",
            type="unknown",
            topology="linear",
            sequence=None,
        )


@pytest.mark.parametrize("topology", ["circular", "linear"])
def test_v1_topology_valid_values(topology: str) -> None:
    entry = Entry(
        id="test",
        name="test",
        type="chromosome",
        topology=topology,
        sequence=None,
    )
    assert entry.topology == topology


def test_v1_topology_invalid_value_raises() -> None:
    with pytest.raises(ValidationError):
        Entry(
            id="test",
            name="test",
            type="chromosome",
            topology="branched",
            sequence=None,
        )


@pytest.mark.parametrize("category", ["WGS", "GNM"])
def test_v1_trad_submission_category_valid_values(category: str) -> None:
    common = Common(
        SUBMITTER=Submitter.model_construct(
            ab_name=["T,T."],
            contact="Test",
            email="t@t.com",
            institute="Inst",
            country="Japan",
            city="City",
            street="St",
            zip="000",
        ),
        ST_COMMENT=StComment.model_construct(
            tagset_id="Genome-Assembly-Data",
            assembly_method="test",
            sequencing_technology="Illumina",
        ),
        trad_submission_category=category,
    )
    assert common.trad_submission_category == category


def test_v1_trad_submission_category_invalid_value_raises() -> None:
    with pytest.raises(ValidationError):
        Common(
            SUBMITTER=Submitter.model_construct(
                ab_name=["T,T."],
                contact="Test",
                email="t@t.com",
                institute="Inst",
                country="Japan",
                city="City",
                street="St",
                zip="000",
            ),
            ST_COMMENT=StComment.model_construct(
                tagset_id="Genome-Assembly-Data",
                assembly_method="test",
                sequencing_technology="Illumina",
            ),
            trad_submission_category="VRL",
        )


# === extra field behavior ===


def test_v1_common_source_extra_allow() -> None:
    cs = CommonSource(organism="Test", mol_type="genomic DNA", extra_field="value")
    assert cs.model_extra is not None
    assert cs.model_extra["extra_field"] == "value"


def test_v1_entry_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        Entry(
            id="test",
            name="test",
            type="chromosome",
            topology="linear",
            sequence=None,
            unknown_field="value",
        )


def test_v1_common_meta_extra_ignore() -> None:
    cm = CommonMeta(division="BCT", unknown_field="value")
    assert not hasattr(cm, "unknown_field") or cm.model_extra == {}


def test_v1_feature_qualifiers_contain_str_and_bool() -> None:
    feature = Feature(
        id="f1",
        type="CDS",
        location="1..100",
        qualifiers={"pseudo": [True], "product": ["test protein"]},
    )
    assert feature.qualifiers["pseudo"] == [True]
    assert feature.qualifiers["product"] == ["test protein"]
