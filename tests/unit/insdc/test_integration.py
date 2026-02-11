"""Integration tests for INSDC validation via validate_json_data entry point."""

from __future__ import annotations

import copy
from typing import Any

from ddbj_record.validator import validate_json_data

_VALID_V2_RECORD: dict[str, Any] = {
    "schema_version": "v2.0",
    "provenance": {},
    "submission": {},
    "sequences": {
        "common_source": {
            "organism": "Homo sapiens",
            "mol_type": "genomic DNA",
            "qualifiers": {
                "collection_date": [{"value": "2024-01-01"}],
                "geo_loc_name": [{"value": "Japan"}],
            },
        },
        "entries": [
            {
                "id": "seq1",
                "name": "seq1",
                "type": "chromosome",
                "topology": "linear",
                "sequence": "ATCGATCG",
                "source_features": [
                    {"id": "sf1", "location": "1..8"},
                ],
            }
        ],
    },
    "features": [
        {
            "id": "f1",
            "type": "CDS",
            "location": "1..6",
            "sequence_id": "seq1",
            "qualifiers": {
                "product": [{"value": "test protein"}],
                "codon_start": [{"value": "1"}],
                "transl_table": [{"value": "1"}],
            },
        }
    ],
}


def _make_record() -> dict[str, Any]:
    return copy.deepcopy(_VALID_V2_RECORD)


# === Integration: validate_json_data with INSDC ===


def test_validate_json_data_includes_insdc_errors() -> None:
    record = _make_record()
    record["features"][0]["qualifiers"]["codon_start"] = [{"value": "999"}]
    result = validate_json_data(record, "v2")
    assert any(e.type == "invalid_qualifier_value" for e in result.errors)


def test_validate_json_data_no_insdc_validation_skips_insdc() -> None:
    record = _make_record()
    record["features"][0]["qualifiers"]["codon_start"] = [{"value": "999"}]
    result = validate_json_data(record, "v2", no_insdc_validation=True)
    insdc_errors = [e for e in result.errors if e.type == "invalid_qualifier_value"]
    assert insdc_errors == []


def test_validate_json_data_strict_flag() -> None:
    record = _make_record()
    record["features"][0]["qualifiers"]["totally_fake"] = [{"value": "x"}]

    result_lenient = validate_json_data(copy.deepcopy(record), "v2", strict=False)
    result_strict = validate_json_data(copy.deepcopy(record), "v2", strict=True)

    lenient_unknown = [e for e in result_lenient.errors if e.type == "unknown_qualifier_key"]
    strict_unknown = [e for e in result_strict.errors if e.type == "unknown_qualifier_key"]

    assert all(e.severity == "warning" for e in lenient_unknown)
    assert all(e.severity == "error" for e in strict_unknown)


def test_validate_json_data_warning_only_is_valid() -> None:
    record = _make_record()
    # deprecated qualifier (pseudo) should produce warning only
    record["features"][0]["qualifiers"]["pseudo"] = [{"value": "true"}]
    result = validate_json_data(record, "v2")
    deprecated_errors = [e for e in result.errors if e.type == "deprecated_qualifier"]
    if deprecated_errors:
        assert result.valid is True
        assert all(e.severity == "warning" for e in deprecated_errors)


def test_validate_json_data_error_makes_invalid() -> None:
    record = _make_record()
    record["features"][0]["qualifiers"]["codon_start"] = [{"value": "999"}]
    result = validate_json_data(record, "v2")
    has_error = any(e.severity == "error" for e in result.errors)
    if has_error:
        assert result.valid is False
