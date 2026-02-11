import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError as PydanticValidationError

from ddbj_record.validator import (
    ErrorDetail,
    ValidationResult,
    ValidationSummary,
    _validate_referential_integrity,
    main,
    parse_args,
    validate_json_data,
    validate_schema,
)

# === validate_schema: valid data ===


def test_validate_schema_v1_valid_returns_true(v1_valid_minimal: dict[str, Any]) -> None:
    result = validate_schema(v1_valid_minimal, "v1")
    assert result.valid is True
    assert result.errors == []


def test_validate_schema_v2_valid_returns_true(v2_valid_minimal: dict[str, Any]) -> None:
    result = validate_schema(v2_valid_minimal, "v2")
    assert result.valid is True


def test_validate_schema_v1_dfc_gnm_returns_true(v1_valid_dfc_gnm: dict[str, Any]) -> None:
    result = validate_schema(v1_valid_dfc_gnm, "v1")
    assert result.valid is True


def test_validate_schema_v2_dfc_gnm_returns_true(v2_valid_dfc_gnm: dict[str, Any]) -> None:
    result = validate_schema(v2_valid_dfc_gnm, "v2")
    assert result.valid is True


# === validate_schema: valid returns empty errors list ===


def test_validate_schema_valid_returns_empty_errors_list(v2_valid_minimal: dict[str, Any]) -> None:
    result = validate_schema(v2_valid_minimal, "v2")
    assert result.valid is True
    assert result.errors == []


# === validate_schema: invalid data ===


def test_validate_schema_v1_missing_required_returns_false(v1_invalid_missing_required: dict[str, Any]) -> None:
    result = validate_schema(v1_invalid_missing_required, "v1")
    assert result.valid is False
    assert len(result.errors) > 0


def test_validate_schema_v2_missing_required_returns_false(v2_invalid_missing_required: dict[str, Any]) -> None:
    result = validate_schema(v2_invalid_missing_required, "v2")
    assert result.valid is False


def test_validate_schema_v2_wrong_type_returns_false(v2_invalid_wrong_type: dict[str, Any]) -> None:
    result = validate_schema(v2_invalid_wrong_type, "v2")
    assert result.valid is False


def test_validate_schema_v2_extra_field_returns_false(v2_invalid_extra_field: dict[str, Any]) -> None:
    result = validate_schema(v2_invalid_extra_field, "v2")
    assert result.valid is False


# === validate_json_data: referential integrity ===


def test_validate_json_data_valid_passes_all_checks(v2_valid_boolean_qualifier: dict[str, Any]) -> None:
    result = validate_json_data(v2_valid_boolean_qualifier, "v2")
    assert result.valid is True


def test_validate_referential_integrity_duplicate_entry_id() -> None:
    json_data = {
        "sequences": {
            "entries": [
                {"id": "seq1", "source_features": [{"id": "sf1"}]},
                {"id": "seq1", "source_features": [{"id": "sf2"}]},
            ]
        },
        "features": [],
    }
    errors = _validate_referential_integrity(json_data, "v2")
    assert len(errors) == 1
    assert errors[0].type == "duplicate_entry_id"
    assert "seq1" in errors[0].msg


def test_validate_referential_integrity_invalid_sequence_id() -> None:
    json_data = {
        "sequences": {
            "entries": [
                {"id": "seq1", "source_features": [{"id": "sf1"}]},
            ]
        },
        "features": [
            {"sequence_id": "nonexistent"},
        ],
    }
    errors = _validate_referential_integrity(json_data, "v2")
    assert len(errors) == 1
    assert errors[0].type == "invalid_sequence_id_reference"
    assert "nonexistent" in errors[0].msg


def test_validate_json_data_schema_error_skips_referential_integrity(
    v2_invalid_missing_required: dict[str, Any],
) -> None:
    result = validate_json_data(v2_invalid_missing_required, "v2")
    assert result.valid is False
    error_types = [e.type for e in result.errors]
    assert "duplicate_entry_id" not in error_types
    assert "invalid_sequence_id_reference" not in error_types


# === validate_referential_integrity: empty sequence_id is error ===


def test_validate_referential_integrity_empty_sequence_id_is_error() -> None:
    json_data = {
        "sequences": {
            "entries": [
                {"id": "seq1", "source_features": [{"id": "sf1"}]},
            ]
        },
        "features": [
            {"id": "f1", "sequence_id": ""},
        ],
    }
    errors = _validate_referential_integrity(json_data, "v2")
    assert any(e.type == "invalid_sequence_id_reference" for e in errors)


# === validate_referential_integrity: v1 ===


def test_validate_referential_integrity_v1_duplicate_entry_id() -> None:
    json_data = {
        "ENTRIES": [
            {"id": "chr1", "features": [{"id": "sf1", "type": "source"}]},
            {"id": "chr1", "features": [{"id": "sf2", "type": "source"}]},
        ],
    }
    errors = _validate_referential_integrity(json_data, "v1")
    assert any(e.type == "duplicate_entry_id" for e in errors)


def test_validate_referential_integrity_v2_duplicate_feature_id() -> None:
    json_data = {
        "sequences": {"entries": [{"id": "seq1", "source_features": [{"id": "sf1"}]}]},
        "features": [
            {"id": "f1", "sequence_id": "seq1"},
            {"id": "f1", "sequence_id": "seq1"},
        ],
    }
    errors = _validate_referential_integrity(json_data, "v2")
    assert any(e.type == "duplicate_feature_id" for e in errors)


def test_validate_referential_integrity_v1_duplicate_feature_id() -> None:
    json_data = {
        "ENTRIES": [
            {
                "id": "chr1",
                "features": [
                    {"id": "f1", "type": "source"},
                    {"id": "f1", "type": "CDS"},
                ],
            },
        ],
    }
    errors = _validate_referential_integrity(json_data, "v1")
    assert any(e.type == "duplicate_feature_id" for e in errors)


def test_validate_referential_integrity_v1_missing_source_feature() -> None:
    json_data = {
        "ENTRIES": [
            {
                "id": "chr1",
                "features": [
                    {"id": "f1", "type": "CDS"},
                ],
            },
        ],
    }
    errors = _validate_referential_integrity(json_data, "v1")
    assert any(e.type == "missing_source_feature" for e in errors)


# === validate_referential_integrity: v2 source feature ===


def test_validate_referential_integrity_v2_missing_source_feature() -> None:
    json_data = {
        "sequences": {
            "entries": [
                {"id": "seq1", "source_features": []},
            ]
        },
        "features": [],
    }
    errors = _validate_referential_integrity(json_data, "v2")
    assert any(e.type == "missing_source_feature" for e in errors)
    error = next(e for e in errors if e.type == "missing_source_feature")
    assert "seq1" in error.msg


def test_validate_referential_integrity_v2_with_source_feature_passes() -> None:
    json_data = {
        "sequences": {
            "entries": [
                {"id": "seq1", "source_features": [{"id": "sf1"}]},
            ]
        },
        "features": [],
    }
    errors = _validate_referential_integrity(json_data, "v2")
    assert not any(e.type == "missing_source_feature" for e in errors)


def test_validate_referential_integrity_v2_missing_source_feature_key_treated_as_empty() -> None:
    json_data = {
        "sequences": {
            "entries": [
                {"id": "seq1"},
            ]
        },
        "features": [],
    }
    errors = _validate_referential_integrity(json_data, "v2")
    assert any(e.type == "missing_source_feature" for e in errors)


# === schema_version consistency check ===


def test_validate_json_data_schema_version_consistency_check() -> None:
    data = {
        "schema_version": "v1.0",
        "provenance": {},
        "submission": {},
        "sequences": {"common_source": {"organism": "Test", "mol_type": "genomic DNA"}},
    }
    result = validate_json_data(data, "v2")
    assert result.valid is False
    assert any(e.type == "schema_version_mismatch" for e in result.errors)


def test_validate_json_data_v2_with_v1_schema_version_returns_mismatch_error() -> None:
    data = {
        "schema_version": "v1.0",
        "provenance": {},
        "submission": {},
        "sequences": {"common_source": {"organism": "Test", "mol_type": "genomic DNA"}},
    }
    result = validate_json_data(data, "v2")
    assert result.valid is False
    assert result.errors[0].type == "schema_version_mismatch"
    assert "v1.0" in result.errors[0].msg


def test_validate_json_data_legacy_0_2_passes_consistency() -> None:
    data = {
        "schema_version": "0.2",
        "provenance": {},
        "submission": {},
        "sequences": {"common_source": {"organism": "Test", "mol_type": "genomic DNA"}},
    }
    result = validate_json_data(data, "v2")
    assert result.valid is True


def test_validate_json_data_missing_schema_version_key_skips_consistency() -> None:
    # schema_version key is missing -> skip consistency, let Pydantic catch it
    data = {
        "provenance": {},
        "submission": {},
        "sequences": {"common_source": {"organism": "Test", "mol_type": "genomic DNA"}},
    }
    result = validate_json_data(data, "v2")
    assert result.valid is False
    # Should be a schema validation error (missing), not a version mismatch
    assert all(e.type != "schema_version_mismatch" for e in result.errors)


def test_validate_json_data_normalizes_legacy_value_before_pydantic() -> None:
    data = {
        "schema_version": "0.2",
        "provenance": {},
        "submission": {},
        "sequences": {"common_source": {"organism": "Test", "mol_type": "genomic DNA"}},
    }
    validate_json_data(data, "v2")
    # After validation, the dict should have normalized value (latest minor)
    assert data["schema_version"] == "v2.1"


# === parse_args ===


def test_parse_args_valid_version_and_input(tmp_path: Path) -> None:
    input_file = tmp_path.joinpath("test.json")
    input_file.write_text("{}")
    args = parse_args(["--version", "v2", "--input", str(input_file)])
    assert args.version == "v2"
    assert args.input == input_file


def test_parse_args_minor_version_normalized_to_major(tmp_path: Path) -> None:
    input_file = tmp_path.joinpath("test.json")
    input_file.write_text("{}")
    args = parse_args(["--version", "v2.0", "--input", str(input_file)])
    assert args.version == "v2"


def test_parse_args_invalid_version_raises(tmp_path: Path) -> None:
    input_file = tmp_path.joinpath("test.json")
    input_file.write_text("{}")
    with pytest.raises(SystemExit):
        parse_args(["--version", "v999", "--input", str(input_file)])


def test_parse_args_nonexistent_input_raises() -> None:
    with pytest.raises(SystemExit):
        parse_args(["--version", "v2", "--input", "/nonexistent/path.json"])


def test_parse_args_no_fail_fast_flag(tmp_path: Path) -> None:
    input_file = tmp_path.joinpath("test.json")
    input_file.write_text("{}")
    args = parse_args(["--version", "v2", "--input", str(input_file), "--no-fail-fast"])
    assert args.fail_fast is False


def test_parse_args_default_fail_fast_is_true(tmp_path: Path) -> None:
    input_file = tmp_path.joinpath("test.json")
    input_file.write_text("{}")
    args = parse_args(["--version", "v2", "--input", str(input_file)])
    assert args.fail_fast is True


# === main: exit codes ===


def test_main_exits_1_on_validation_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_file = tmp_path.joinpath("invalid.json")
    input_file.write_text('{"schema_version": "v2.0"}')
    monkeypatch.setattr("sys.argv", ["prog", "--version", "v2", "--input", str(input_file)])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1


def test_main_exits_0_on_validation_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, v2_valid_minimal: dict[str, Any]
) -> None:
    input_file = tmp_path.joinpath("valid.json")
    input_file.write_text(json.dumps(v2_valid_minimal))
    monkeypatch.setattr("sys.argv", ["prog", "--version", "v2", "--input", str(input_file)])
    # Should not raise SystemExit (exit code 0 means no exception)
    main()


def test_main_exits_1_on_json_parse_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_file = tmp_path.joinpath("bad.json")
    input_file.write_text("{not valid json")
    monkeypatch.setattr("sys.argv", ["prog", "--version", "v2", "--input", str(input_file)])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1


def test_main_json_parse_error_outputs_validation_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    input_file = tmp_path.joinpath("bad.json")
    input_file.write_text("{not valid json")
    monkeypatch.setattr("sys.argv", ["prog", "--version", "v2", "--input", str(input_file)])
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["valid"] is False
    assert output["errors"][0]["type"] == "json_parse_error"


# === ErrorDetail field validation ===


def test_error_detail_severity_rejects_invalid_value() -> None:
    with pytest.raises(PydanticValidationError):
        ErrorDetail(type="test", loc=[], msg="test", severity="critical")


def test_error_detail_severity_accepts_error() -> None:
    e = ErrorDetail(type="test", loc=[], msg="test", severity="error")
    assert e.severity == "error"


def test_error_detail_severity_accepts_warning() -> None:
    e = ErrorDetail(type="test", loc=[], msg="test", severity="warning")
    assert e.severity == "warning"


def test_error_detail_severity_defaults_to_error() -> None:
    e = ErrorDetail(type="test", loc=[], msg="test")
    assert e.severity == "error"


def test_error_detail_context_defaults_to_none() -> None:
    e = ErrorDetail(type="test", loc=[], msg="test")
    assert e.context is None


def test_error_detail_context_accepts_dict() -> None:
    e = ErrorDetail(type="test", loc=[], msg="test", context={"key": "value"})
    assert e.context == {"key": "value"}


def test_error_detail_stage_defaults_to_none() -> None:
    e = ErrorDetail(type="test", loc=[], msg="test")
    assert e.stage is None


def test_error_detail_stage_accepts_string() -> None:
    e = ErrorDetail(type="test", loc=[], msg="test", stage="schema")
    assert e.stage == "schema"


# === ValidationSummary / ValidationResult computed fields ===


def test_validation_result_submittable_true_when_no_errors() -> None:
    result = ValidationResult(valid=True, errors=[])
    assert result.submittable is True


def test_validation_result_submittable_true_when_warnings_only() -> None:
    result = ValidationResult(
        valid=True,
        errors=[ErrorDetail(type="test", loc=[], msg="warn", severity="warning")],
    )
    assert result.submittable is True


def test_validation_result_submittable_false_when_error_exists() -> None:
    result = ValidationResult(
        valid=False,
        errors=[ErrorDetail(type="test", loc=[], msg="err", severity="error")],
    )
    assert result.submittable is False


def test_validation_result_submittable_false_with_mixed_severities() -> None:
    result = ValidationResult(
        valid=False,
        errors=[
            ErrorDetail(type="w", loc=[], msg="warn", severity="warning"),
            ErrorDetail(type="e", loc=[], msg="err", severity="error"),
        ],
    )
    assert result.submittable is False


def test_validation_result_summary_empty() -> None:
    result = ValidationResult(valid=True, errors=[])
    assert result.summary == ValidationSummary(error_count=0, warning_count=0)


def test_validation_result_summary_counts_correctly() -> None:
    result = ValidationResult(
        valid=False,
        errors=[
            ErrorDetail(type="e1", loc=[], msg="err1", severity="error"),
            ErrorDetail(type="e2", loc=[], msg="err2", severity="error"),
            ErrorDetail(type="w1", loc=[], msg="warn1", severity="warning"),
        ],
    )
    assert result.summary.error_count == 2
    assert result.summary.warning_count == 1


def test_validation_result_json_includes_submittable_and_summary() -> None:
    result = ValidationResult(
        valid=False,
        errors=[ErrorDetail(type="e", loc=[], msg="err", severity="error")],
    )
    output = json.loads(result.model_dump_json())
    assert "submittable" in output
    assert output["submittable"] is False
    assert "summary" in output
    assert output["summary"]["error_count"] == 1
    assert output["summary"]["warning_count"] == 0


# === fail_fast option ===


def _make_data_with_ref_and_insdc_errors() -> dict[str, Any]:
    """Create v2 data that triggers both referential integrity and INSDC errors."""
    return {
        "schema_version": "v2.0",
        "provenance": {"source_format": "GFF"},
        "submission": {
            "submitters": [],
            "db_xrefs": [],
            "references": [],
            "comments": [],
        },
        "sequences": {
            "common_source": {"organism": "Test", "mol_type": "genomic DNA"},
            "entries": [
                {
                    "id": "seq1",
                    "name": "seq1",
                    "type": "chromosome",
                    "topology": "linear",
                    "source_features": [{"id": "sf1", "location": "1..100"}],
                },
                {
                    "id": "seq1",  # duplicate entry id -> referential integrity error
                    "name": "seq2",
                    "type": "chromosome",
                    "topology": "linear",
                    "source_features": [{"id": "sf2", "location": "1..100"}],
                },
            ],
        },
        "features": [
            {
                "id": "f1",
                "type": "FAKE_FEATURE",  # unknown feature -> INSDC error
                "location": "1..100",
                "sequence_id": "seq1",
                "qualifiers": {},
            },
        ],
    }


def test_fail_fast_true_stops_at_stage3() -> None:
    data = _make_data_with_ref_and_insdc_errors()
    result = validate_json_data(data, "v2", fail_fast=True)
    assert result.valid is False
    stages = {e.stage for e in result.errors}
    assert "referential_integrity" in stages
    assert "insdc" not in stages


def test_fail_fast_false_collects_all_stages() -> None:
    data = _make_data_with_ref_and_insdc_errors()
    result = validate_json_data(data, "v2", fail_fast=False)
    assert result.valid is False
    stages = {e.stage for e in result.errors}
    assert "referential_integrity" in stages
    assert "insdc" in stages


def test_fail_fast_default_is_true() -> None:
    data = _make_data_with_ref_and_insdc_errors()
    result = validate_json_data(data, "v2")
    stages = {e.stage for e in result.errors}
    assert "referential_integrity" in stages
    assert "insdc" not in stages


def test_fail_fast_false_with_only_insdc_warnings() -> None:
    data = {
        "schema_version": "v2.0",
        "provenance": {"source_format": "GFF"},
        "submission": {
            "submitters": [],
            "db_xrefs": [],
            "references": [],
            "comments": [],
        },
        "sequences": {
            "common_source": {"organism": "Test", "mol_type": "genomic DNA"},
            "entries": [
                {
                    "id": "seq1",
                    "name": "seq1",
                    "type": "chromosome",
                    "topology": "linear",
                    "source_features": [{"id": "sf1", "location": "1..100"}],
                },
            ],
        },
        "features": [
            {
                "id": "f1",
                "type": "FAKE_FEATURE",
                "location": "1..100",
                "sequence_id": "seq1",
                "qualifiers": {},
            },
        ],
    }
    result = validate_json_data(data, "v2", fail_fast=False)
    # unknown feature key in lenient mode is a warning, not an error
    assert result.valid is True
    assert any(e.type == "unknown_feature_key" for e in result.errors)


# === stage field on validate_json_data outputs ===


def test_schema_version_mismatch_has_stage() -> None:
    data = {
        "schema_version": "v1.0",
        "provenance": {},
        "submission": {},
        "sequences": {"common_source": {"organism": "Test", "mol_type": "genomic DNA"}},
    }
    result = validate_json_data(data, "v2")
    assert result.errors[0].stage == "schema_version"


def test_schema_validation_error_has_stage(v2_invalid_missing_required: dict[str, Any]) -> None:
    result = validate_json_data(v2_invalid_missing_required, "v2")
    for e in result.errors:
        assert e.stage == "schema"


def test_referential_integrity_error_has_stage() -> None:
    data = {
        "sequences": {
            "entries": [
                {"id": "seq1", "source_features": [{"id": "sf1"}]},
                {"id": "seq1", "source_features": [{"id": "sf2"}]},
            ]
        },
        "features": [],
    }
    errors = _validate_referential_integrity(data, "v2")
    for e in errors:
        assert e.stage == "referential_integrity"


def test_insdc_validation_error_has_stage(v2_valid_minimal: dict[str, Any]) -> None:
    v2_valid_minimal["features"] = [
        {"id": "f1", "type": "FAKE", "sequence_id": "seq1", "qualifiers": {}},
    ]
    result = validate_json_data(v2_valid_minimal, "v2")
    insdc_errors = [e for e in result.errors if e.type == "unknown_feature_key"]
    for e in insdc_errors:
        assert e.stage == "insdc"


def test_json_parse_error_has_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    input_file = tmp_path.joinpath("bad.json")
    input_file.write_text("{not valid json")
    monkeypatch.setattr("sys.argv", ["prog", "--version", "v2", "--input", str(input_file)])
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["errors"][0]["stage"] == "schema"


# === Pydantic type constraint tests (v2.1) ===


def _make_v2_data(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create minimal valid v2 data for constraint testing."""
    data: dict[str, Any] = {
        "schema_version": "v2.0",
        "provenance": {},
        "submission": {
            "references": [
                {
                    "title": "Test",
                    "authors": [],
                    "status": "unpublished",
                    "year": "2025",
                }
            ],
        },
        "sequences": {
            "common_source": {"organism": "Test", "mol_type": "genomic DNA"},
            "entries": [
                {
                    "id": "seq1",
                    "name": "seq1",
                    "type": "chromosome",
                    "topology": "linear",
                    "source_features": [{"id": "sf1", "location": "1..100"}],
                },
            ],
        },
        "features": [],
    }
    if overrides:
        _apply_overrides(data, overrides)

    return data


def _apply_overrides(data: dict[str, Any], overrides: dict[str, Any]) -> None:
    """Apply nested overrides using dot notation."""
    for key, value in overrides.items():
        keys = key.split(".")
        target = data
        for k in keys[:-1]:
            target = target[int(k)] if k.isdigit() else target[k]
        last_key = keys[-1]
        target[int(last_key) if last_key.isdigit() else last_key] = value


# --- trad_submission_category ---


def test_trad_submission_category_invalid_value_rejected() -> None:
    data = _make_v2_data({"submission.trad_submission_category": "INVALID"})
    result = validate_schema(data, "v2")
    assert result.valid is False


@pytest.mark.parametrize("value", ["WGS", "GNM", None])
def test_trad_submission_category_valid_values_accepted(value: str | None) -> None:
    data = _make_v2_data({"submission.trad_submission_category": value})
    result = validate_schema(data, "v2")
    assert result.valid is True


# --- hold_date ---


def test_hold_date_invalid_format_rejected() -> None:
    data = _make_v2_data({"submission.hold_date": "not-a-date"})
    result = validate_schema(data, "v2")
    assert result.valid is False


def test_hold_date_valid_format_accepted() -> None:
    data = _make_v2_data({"submission.hold_date": "2025-01-01"})
    result = validate_schema(data, "v2")
    assert result.valid is True


# --- year ---


def test_year_invalid_format_rejected() -> None:
    data = _make_v2_data({"submission.references.0.year": "abcd"})
    result = validate_schema(data, "v2")
    assert result.valid is False


def test_year_valid_format_accepted() -> None:
    data = _make_v2_data({"submission.references.0.year": "2025"})
    result = validate_schema(data, "v2")
    assert result.valid is True


def test_year_empty_string_accepted() -> None:
    data = _make_v2_data({"submission.references.0.year": ""})
    result = validate_schema(data, "v2")
    assert result.valid is True


# --- date_published ---


def test_date_published_wrong_separator_rejected() -> None:
    data = _make_v2_data({"submission.references.0.date_published": "2025/01/01"})
    result = validate_schema(data, "v2")
    assert result.valid is False


def test_date_published_valid_format_accepted() -> None:
    data = _make_v2_data({"submission.references.0.date_published": "2025-01-01"})
    result = validate_schema(data, "v2")
    assert result.valid is True


# --- Entry.id ---


def test_entry_id_too_long_rejected() -> None:
    data = _make_v2_data({"sequences.entries.0.id": "a" * 33})
    result = validate_schema(data, "v2")
    assert result.valid is False


def test_entry_id_empty_rejected() -> None:
    data = _make_v2_data({"sequences.entries.0.id": ""})
    result = validate_schema(data, "v2")
    assert result.valid is False


def test_entry_id_valid_accepted() -> None:
    data = _make_v2_data({"sequences.entries.0.id": "valid_id-1.0"})
    result = validate_schema(data, "v2")
    assert result.valid is True


def test_entry_id_with_space_rejected() -> None:
    data = _make_v2_data({"sequences.entries.0.id": "id with space"})
    result = validate_schema(data, "v2")
    assert result.valid is False


# --- schema_version ---


@pytest.mark.parametrize("version", ["v2.0", "v2.1", "v2", "0.2"])
def test_schema_version_valid_values_accepted(version: str) -> None:
    data = _make_v2_data({"schema_version": version})
    result = validate_schema(data, "v2")
    assert result.valid is True


def test_schema_version_without_v_prefix_rejected() -> None:
    data = _make_v2_data({"schema_version": "2.0"})
    result = validate_schema(data, "v2")
    assert result.valid is False


def test_schema_version_completely_invalid_rejected() -> None:
    data = _make_v2_data({"schema_version": "invalid"})
    result = validate_schema(data, "v2")
    assert result.valid is False


# === Date validity tests ===


def test_hold_date_invalid_day_returns_invalid_date_value() -> None:
    data = _make_v2_data({"submission.hold_date": "2025-02-30"})
    result = validate_json_data(data, "v2")
    assert result.valid is False
    assert any(e.type == "invalid_date_value" for e in result.errors)


def test_hold_date_invalid_month_returns_invalid_date_value() -> None:
    data = _make_v2_data({"submission.hold_date": "2025-13-01"})
    result = validate_json_data(data, "v2")
    assert result.valid is False
    assert any(e.type == "invalid_date_value" for e in result.errors)


def test_hold_date_valid_passes() -> None:
    data = _make_v2_data({"submission.hold_date": "2025-01-01"})
    result = validate_json_data(data, "v2")
    assert result.valid is True


def test_date_published_invalid_day_returns_invalid_date_value() -> None:
    data = _make_v2_data({"submission.references.0.date_published": "2025-06-31"})
    result = validate_json_data(data, "v2")
    assert result.valid is False
    assert any(e.type == "invalid_date_value" for e in result.errors)


def test_date_published_leap_year_valid() -> None:
    data = _make_v2_data({"submission.references.0.date_published": "2024-02-29"})
    result = validate_json_data(data, "v2")
    assert result.valid is True


def test_date_published_non_leap_year_feb29_invalid() -> None:
    data = _make_v2_data({"submission.references.0.date_published": "2025-02-29"})
    result = validate_json_data(data, "v2")
    assert result.valid is False
    assert any(e.type == "invalid_date_value" for e in result.errors)


# === Boundary value tests ===


def test_entry_id_max_length_32_accepted() -> None:
    data = _make_v2_data({"sequences.entries.0.id": "a" * 32})
    result = validate_schema(data, "v2")
    assert result.valid is True


def test_year_boundary_0000_accepted() -> None:
    data = _make_v2_data({"submission.references.0.year": "0000"})
    result = validate_schema(data, "v2")
    assert result.valid is True


def test_year_boundary_9999_accepted() -> None:
    data = _make_v2_data({"submission.references.0.year": "9999"})
    result = validate_schema(data, "v2")
    assert result.valid is True


def test_hold_date_year_0000_checked_by_fromisoformat() -> None:
    data = _make_v2_data({"submission.hold_date": "0000-01-01"})
    result = validate_json_data(data, "v2")
    # Python's date.fromisoformat rejects year 0000 (MINYEAR=1)
    assert result.valid is False
    assert any(e.type == "invalid_date_value" for e in result.errors)
