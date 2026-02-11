"""DDBJ Record Validator CLI.

Command-line interface for validating DDBJ record JSON files against schema specifications.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from ddbj_record.schema import LATEST_VERSION, LEGACY_SCHEMA_VERSION_MAP, SCHEMA_VERSIONS, normalize_cli_version
from ddbj_record.utils import resolve_record_model

# === Type Definitions for Validation ===


class ErrorDetail(BaseModel):
    type: str
    loc: list[str | int]
    msg: str
    severity: str = "error"


class ValidationResult(BaseModel):
    valid: bool
    errors: list[ErrorDetail] = []


# =======================================


class Args(BaseModel):
    """Command line arguments for the validator."""

    version: str
    input: Path
    no_insdc_validation: bool = False
    strict: bool = False


def parse_args(args: list[str] | None = None) -> Args:
    parser = argparse.ArgumentParser(
        description="DDBJ record - validates JSON file against specified schema version",
        epilog="Example: %(prog)s --version v1 --input sample_record.json",
    )

    parser.add_argument(
        "-v",
        "--version",
        type=str,
        default=LATEST_VERSION,
        help=f"Schema version to dump ({', '.join(SCHEMA_VERSIONS)})",
    )

    parser.add_argument("-i", "--input", type=Path, required=True, help="Path to JSON file to validate")
    parser.add_argument("--no-insdc-validation", action="store_true", help="Skip INSDC feature/qualifier validation")
    parser.add_argument("--strict", action="store_true", help="Treat unknown feature/qualifier keys as errors")

    if args is None:
        args = sys.argv[1:]

    parsed_args = parser.parse_args(args)
    normalized_version = normalize_cli_version(parsed_args.version)
    if normalized_version is None:
        parser.error(
            f"Invalid schema version: {parsed_args.version}. Supported versions are: {', '.join(SCHEMA_VERSIONS)}"
        )
    if not parsed_args.input.exists():
        parser.error(f"JSON file does not exist: {parsed_args.input}")

    return Args(
        version=normalized_version,
        input=parsed_args.input,
        no_insdc_validation=parsed_args.no_insdc_validation,
        strict=parsed_args.strict,
    )


def validate_schema(json_data: dict[str, Any], schema_version: str) -> ValidationResult:
    record_model = resolve_record_model(schema_version)

    try:
        record_model.model_validate(json_data)
        return ValidationResult(valid=True)
    except ValidationError as e:
        errors: list[ErrorDetail] = []
        for err in e.errors():
            error_detail = ErrorDetail(
                type=err.get("type", "validation_error"),
                loc=list(err.get("loc", [])),
                msg=err.get("msg", ""),
            )
            errors.append(error_detail)

        return ValidationResult(valid=False, errors=errors)


def _validate_referential_integrity(json_data: dict[str, Any], schema_version: str) -> list[ErrorDetail]:
    """Validate cross-field referential integrity constraints."""
    errors: list[ErrorDetail] = []

    if schema_version == "v2":
        # v2: sequences.entries[].id duplicate check
        sequences = json_data.get("sequences", {})
        entries = sequences.get("entries", [])
        entry_ids: set[str] = set()
        for i, entry in enumerate(entries):
            entry_id = entry.get("id", "")
            if entry_id in entry_ids:
                errors.append(
                    ErrorDetail(
                        type="duplicate_entry_id",
                        loc=["sequences", "entries", i, "id"],
                        msg=f"Duplicate entry id: '{entry_id}'",
                    )
                )
            entry_ids.add(entry_id)

        # v2: features[].id duplicate check
        features = json_data.get("features", [])
        feature_ids: set[str] = set()
        for i, feature in enumerate(features):
            feat_id = feature.get("id", "")
            if feat_id in feature_ids:
                errors.append(
                    ErrorDetail(
                        type="duplicate_feature_id",
                        loc=["features", i, "id"],
                        msg=f"Duplicate feature id: '{feat_id}'",
                    )
                )
            feature_ids.add(feat_id)

        # v2: feature.sequence_id reference check
        for i, feature in enumerate(features):
            seq_id = feature.get("sequence_id", "")
            if seq_id not in entry_ids:
                errors.append(
                    ErrorDetail(
                        type="invalid_sequence_id_reference",
                        loc=["features", i, "sequence_id"],
                        msg=f"sequence_id '{seq_id}' does not match any sequences.entries[].id",
                    )
                )

        # v2: entry source feature existence check
        for i, entry in enumerate(entries):
            source_features = entry.get("source_features", [])
            if not source_features:
                entry_id = entry.get("id", "")
                errors.append(
                    ErrorDetail(
                        type="missing_source_feature",
                        loc=["sequences", "entries", i, "source_features"],
                        msg=f"Entry '{entry_id}' has no source feature",
                    )
                )

    elif schema_version == "v1":
        # v1: ENTRIES[].id duplicate check
        v1_entries = json_data.get("ENTRIES", [])
        entry_ids_v1: set[str] = set()
        for i, entry in enumerate(v1_entries):
            entry_id = entry.get("id", "")
            if entry_id in entry_ids_v1:
                errors.append(
                    ErrorDetail(
                        type="duplicate_entry_id",
                        loc=["ENTRIES", i, "id"],
                        msg=f"Duplicate entry id: '{entry_id}'",
                    )
                )
            entry_ids_v1.add(entry_id)

        # v1: feature ID duplicate check across all entries + source feature existence
        feature_ids_v1: set[str] = set()
        for entry_idx, entry in enumerate(v1_entries):
            features = entry.get("features", [])
            has_source = False
            for feat_idx, feature in enumerate(features):
                feat_id = feature.get("id", "")
                if feat_id in feature_ids_v1:
                    errors.append(
                        ErrorDetail(
                            type="duplicate_feature_id",
                            loc=["ENTRIES", entry_idx, "features", feat_idx, "id"],
                            msg=f"Duplicate feature id: '{feat_id}'",
                        )
                    )
                feature_ids_v1.add(feat_id)
                if feature.get("type") == "source":
                    has_source = True
            if not has_source:
                entry_id = entry.get("id", "")
                errors.append(
                    ErrorDetail(
                        type="missing_source_feature",
                        loc=["ENTRIES", entry_idx, "features"],
                        msg=f"Entry '{entry_id}' has no source feature",
                    )
                )

    return errors


def _validate_schema_version_consistency(json_data: dict[str, Any], schema_version: str) -> list[ErrorDetail]:
    """Check that json_data's schema_version is consistent with the specified version."""
    raw_version = json_data.get("schema_version")
    if raw_version is None:
        return []

    normalized = LEGACY_SCHEMA_VERSION_MAP.get(raw_version, raw_version)
    # Write back normalized value so Pydantic doesn't see the legacy value
    json_data["schema_version"] = normalized

    prefix = f"{schema_version}."
    if not normalized.startswith(prefix):
        return [
            ErrorDetail(
                type="schema_version_mismatch",
                loc=["schema_version"],
                msg=f"schema_version '{raw_version}' is not compatible with specified version '{schema_version}'",
            )
        ]

    return []


def validate_json_data(
    json_data: dict[str, Any],
    schema_version: str,
    *,
    no_insdc_validation: bool = False,
    strict: bool = False,
) -> ValidationResult:
    # 1. schema_version consistency check + legacy normalization
    version_errors = _validate_schema_version_consistency(json_data, schema_version)
    if version_errors:
        return ValidationResult(valid=False, errors=version_errors)

    # 2. Validate against schema
    validation_result = validate_schema(json_data, schema_version)
    if not validation_result.valid:
        return validation_result

    # 3. Validate referential integrity
    ref_errors = _validate_referential_integrity(json_data, schema_version)
    if ref_errors:
        return ValidationResult(valid=False, errors=ref_errors)

    # 4. Validate against INSDC feature / qualifier tables
    if not no_insdc_validation:
        insdc_errors = _validate_insdc(json_data, schema_version, strict=strict)
        if insdc_errors:
            has_errors = any(e.severity == "error" for e in insdc_errors)

            return ValidationResult(valid=not has_errors, errors=insdc_errors)

    return ValidationResult(valid=True)


def _validate_insdc(json_data: dict[str, Any], schema_version: str, *, strict: bool) -> list[ErrorDetail]:
    from ddbj_record.insdc.validator import validate_insdc_v1, validate_insdc_v2

    if schema_version == "v2":
        return validate_insdc_v2(json_data, strict=strict)
    if schema_version == "v1":
        return validate_insdc_v1(json_data, strict=strict)

    return []


def main() -> None:
    try:
        args = parse_args(sys.argv[1:])
    except SystemExit:
        raise
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        with args.input.open("r", encoding="utf-8") as f:
            json_data = json.load(f)
    except json.JSONDecodeError as e:
        result = ValidationResult(
            valid=False,
            errors=[ErrorDetail(type="json_parse_error", loc=[], msg=str(e))],
        )
        print(result.model_dump_json(indent=2))
        sys.exit(1)

    try:
        validation_result = validate_json_data(
            json_data, args.version,
            no_insdc_validation=args.no_insdc_validation,
            strict=args.strict,
        )
        print(validation_result.model_dump_json(indent=2))
        if not validation_result.valid:
            sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
