from typing import Any

import pytest
from pydantic import ValidationError

from ddbj_record.schema.v2 import (
    Address,
    DdbjRecord,
    Design,
    Entry,
    LibraryLayout,
    Organization,
    Person,
    Provenance,
    Qualifier,
    Reference,
    Submission,
)
from ddbj_record.validator import validate_json_data

# === valid fixture parsing ===


def test_v2_valid_minimal_parses(v2_valid_minimal: dict[str, Any]) -> None:
    record = DdbjRecord.model_validate(v2_valid_minimal)
    assert record.schema_version == "v2.3"


def test_v2_valid_dfc_gnm_parses(v2_valid_dfc_gnm: dict[str, Any]) -> None:
    record = DdbjRecord.model_validate(v2_valid_dfc_gnm)
    assert len(record.sequences.entries) > 0


def test_v2_valid_wf_dfc_wgs_parses(v2_valid_wf_dfc_wgs: dict[str, Any]) -> None:
    record = DdbjRecord.model_validate(v2_valid_wf_dfc_wgs)
    assert record.submission is not None
    assert len(record.submission.submitters) > 0
    assert len(record.sequences.entries) > 0


def test_v2_valid_dfv_parses(v2_valid_dfv: dict[str, Any]) -> None:
    record = DdbjRecord.model_validate(v2_valid_dfv)
    assert record.schema_version == "v2.3"


def test_v2_valid_wf_dfv_parses(v2_valid_wf_dfv: dict[str, Any]) -> None:
    record = DdbjRecord.model_validate(v2_valid_wf_dfv)
    assert record.schema_version == "v2.3"


def test_v2_valid_boolean_qualifier_parses(v2_valid_boolean_qualifier: dict[str, Any]) -> None:
    record = DdbjRecord.model_validate(v2_valid_boolean_qualifier)
    pseudo_qualifiers = record.features[0].qualifiers.get("pseudo", [])
    assert len(pseudo_qualifiers) > 0
    assert pseudo_qualifiers[0].value == "true"


def test_v2_valid_complex_location_parses(v2_valid_complex_location: dict[str, Any]) -> None:
    record = DdbjRecord.model_validate(v2_valid_complex_location)
    locations = [f.location for f in record.features]
    assert "join(1..30,40..60)" in locations
    assert "complement(join(10..30,50..70))" in locations


def test_v2_valid_multi_source_parses(v2_valid_multi_source: dict[str, Any]) -> None:
    record = DdbjRecord.model_validate(v2_valid_multi_source)
    entry = record.sequences.entries[0]
    assert len(entry.source_features) == 2


# === invalid fixture detection ===


def test_v2_invalid_missing_required_raises(v2_invalid_missing_required: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        DdbjRecord.model_validate(v2_invalid_missing_required)


def test_v2_invalid_wrong_type_raises(v2_invalid_wrong_type: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        DdbjRecord.model_validate(v2_invalid_wrong_type)


def test_v2_invalid_extra_field_raises(v2_invalid_extra_field: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        DdbjRecord.model_validate(v2_invalid_extra_field)


# === legacy schema_version normalization (via validate_json_data) ===


def test_v2_legacy_schema_version_normalized(v2_legacy_schema_version: dict[str, Any]) -> None:
    result = validate_json_data(v2_legacy_schema_version, "v2")
    assert result.valid is True
    assert v2_legacy_schema_version["schema_version"] == "v2.3"


def test_v2_schema_version_02_normalized() -> None:
    data = {
        "schema_version": "0.2",
        "provenance": {},
        "submission": {"submitters": [], "db_xrefs": [], "references": [], "comments": []},
        "experiments": [],
        "sequences": {
            "common_source": {"organism": "Test", "mol_type": "genomic DNA", "qualifiers": {}},
            "entries": [],
        },
        "features": [],
    }
    result = validate_json_data(data, "v2")
    assert result.valid is True
    assert data["schema_version"] == "v2.3"


def test_v2_schema_version_v2_normalized() -> None:
    data = {
        "schema_version": "v2",
        "provenance": {},
        "submission": {"submitters": [], "db_xrefs": [], "references": [], "comments": []},
        "experiments": [],
        "sequences": {
            "common_source": {"organism": "Test", "mol_type": "genomic DNA", "qualifiers": {}},
            "entries": [],
        },
        "features": [],
    }
    result = validate_json_data(data, "v2")
    assert result.valid is True
    assert data["schema_version"] == "v2.3"


# === Literal type boundary values ===


@pytest.mark.parametrize("entry_type", ["chromosome", "plasmid", "unplaced", "other"])
def test_v2_entry_type_valid_values(entry_type: str) -> None:
    entry = Entry(
        id="test",
        name="test",
        type=entry_type,
        topology="linear",
        sequence=None,
        source_features=[],
    )
    assert entry.type == entry_type


def test_v2_entry_type_invalid_value_raises() -> None:
    with pytest.raises(ValidationError):
        Entry(
            id="test",
            name="test",
            type="unknown",
            topology="linear",
            sequence=None,
            source_features=[],
        )


@pytest.mark.parametrize("status", ["unpublished", "in-press", "published"])
def test_v2_reference_status_valid_values(status: str) -> None:
    ref = Reference(title="Test", authors=[], status=status, year="2025")
    assert ref.status == status


def test_v2_reference_status_invalid_value_raises() -> None:
    with pytest.raises(ValidationError):
        Reference(title="Test", authors=[], status="draft", year="2025")


@pytest.mark.parametrize(
    "org_type",
    ["institution", "company", "government", "non-profit", "consortium", "other"],
)
def test_v2_organization_type_valid_values(org_type: str) -> None:
    org = Organization(name="Test Org", type=org_type)
    assert org.type == org_type


@pytest.mark.parametrize("layout_type", ["SINGLE", "PAIRED"])
def test_v2_layout_type_valid_values(layout_type: str) -> None:
    layout = LibraryLayout(layout_type=layout_type)
    assert layout.layout_type == layout_type


def test_v2_library_strategy_valid_value() -> None:
    design = Design(library_strategy="WGS")
    assert design.library_strategy == "WGS"


def test_v2_library_strategy_invalid_value_raises() -> None:
    with pytest.raises(ValidationError):
        Design(library_strategy="INVALID_STRATEGY")


# === extra field behavior ===


def test_v2_provenance_extra_allow() -> None:
    prov = Provenance(source_format="GFF", custom_key="custom_value")
    assert prov.model_extra is not None
    assert prov.model_extra["custom_key"] == "custom_value"


def test_v2_submission_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        Submission(submitters=[], db_xrefs=[], references=[], comments=[], unknown_field="value")  # type: ignore[call-arg]


def test_v2_address_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        Address(country="Japan", city="Tokyo", extra="bad")  # type: ignore[call-arg]


def test_v2_person_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        Person(name="Test", extra="bad")  # type: ignore[call-arg]


# === Qualifier.value is always str ===


def test_v2_qualifier_value_is_always_str() -> None:
    q = Qualifier(value="true")
    assert isinstance(q.value, str)
    assert q.value == "true"


def test_v2_qualifier_value_numeric_str() -> None:
    q = Qualifier(value="11")
    assert isinstance(q.value, str)


# === boundary value tests ===


def test_v2_qualifier_empty_string_value_valid() -> None:
    q = Qualifier(value="")
    assert q.value == ""


def test_v2_person_all_none_fields_valid() -> None:
    person = Person()
    assert person.name is None
    assert person.abbreviation is None
    assert person.email is None
    assert person.orcid is None
    assert person.organization is None


def test_v2_submission_empty_submitters_list_valid() -> None:
    sub = Submission(submitters=[], db_xrefs=[], references=[], comments=[])
    assert sub.submitters == []


def test_v2_entry_comments_none_vs_empty_list() -> None:
    entry_none = Entry(id="e1", name="e1", type="chromosome", topology="linear", source_features=[])
    entry_empty = Entry(id="e2", name="e2", type="chromosome", topology="linear", source_features=[], comments=[])
    assert entry_none.comments is None
    assert entry_empty.comments == []


# === error path detail tests ===


def test_v2_invalid_missing_required_has_missing_type(v2_invalid_missing_required: dict[str, Any]) -> None:
    with pytest.raises(ValidationError) as exc_info:
        DdbjRecord.model_validate(v2_invalid_missing_required)
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any(e["type"] == "missing" for e in errors)


def test_v2_invalid_extra_field_has_extra_forbidden_type(v2_invalid_extra_field: dict[str, Any]) -> None:
    with pytest.raises(ValidationError) as exc_info:
        DdbjRecord.model_validate(v2_invalid_extra_field)
    errors = exc_info.value.errors()
    assert len(errors) > 0
    assert any(e["type"] == "extra_forbidden" for e in errors)


# === KEYWORD / DATATYPE ===


def test_v2_valid_wgs_with_keyword_parses(v2_valid_wgs_with_keyword: dict[str, Any]) -> None:
    record = DdbjRecord.model_validate(v2_valid_wgs_with_keyword)
    assert record.submission.keywords == ["WGS", "STANDARD_DRAFT"]
    assert record.submission.datatype == "WGS"


def test_v2_submission_keywords_none_by_default() -> None:
    sub = Submission(submitters=[], db_xrefs=[], references=[], comments=[])
    assert sub.keywords is None
    assert sub.datatype is None


def test_v2_submission_keywords_list() -> None:
    sub = Submission(submitters=[], db_xrefs=[], references=[], comments=[], keywords=["WGS", "STANDARD_DRAFT"])
    assert sub.keywords == ["WGS", "STANDARD_DRAFT"]


def test_v2_submission_keywords_empty_list() -> None:
    sub = Submission(submitters=[], db_xrefs=[], references=[], comments=[], keywords=[])
    assert sub.keywords == []


def test_v2_submission_datatype_str() -> None:
    sub = Submission(submitters=[], db_xrefs=[], references=[], comments=[], datatype="WGS")
    assert sub.datatype == "WGS"
