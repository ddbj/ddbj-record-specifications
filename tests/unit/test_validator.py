import json
from pathlib import Path
from typing import Any

import pytest

from ddbj_record.validator import (
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
    # After validation, the dict should have normalized value
    assert data["schema_version"] == "v2.0"


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
