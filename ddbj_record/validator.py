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

from ddbj_record.schema import LATEST_VERSION, SCHEMA_VERSIONS
from ddbj_record.utils import resolve_record_model

# === Type Definitions for Validation ===


class ErrorDetail(BaseModel):
    type: str
    loc: list[str | int]
    msg: str


class ValidationResult(BaseModel):
    valid: bool
    errors: list[ErrorDetail] | None = None


# =======================================


class Args(BaseModel):
    """Command line arguments for the validator."""

    version: str
    input: Path


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

    if args is None:
        args = sys.argv[1:]

    parsed_args = parser.parse_args(args)
    if parsed_args.version not in SCHEMA_VERSIONS:
        parser.error(
            f"Invalid schema version: {parsed_args.version}. Supported versions are: {', '.join(SCHEMA_VERSIONS)}"
        )
    if not parsed_args.input.exists():
        parser.error(f"JSON file does not exist: {parsed_args.input}")

    return Args(
        version=parsed_args.version,
        input=parsed_args.input,
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


def _validate_referential_integrity(json_data: dict[str, Any]) -> list[ErrorDetail]:
    """Validate cross-field referential integrity constraints."""
    errors: list[ErrorDetail] = []

    # Collect entry IDs
    sequences = json_data.get("sequences", {})
    entries = sequences.get("entries", [])
    entry_ids: set[str] = set()
    for i, entry in enumerate(entries):
        entry_id = entry.get("id", "")
        if entry_id in entry_ids:
            errors.append(ErrorDetail(
                type="duplicate_entry_id",
                loc=["sequences", "entries", i, "id"],
                msg=f"Duplicate entry id: '{entry_id}'",
            ))
        entry_ids.add(entry_id)

    # Validate feature.sequence_id references
    features = json_data.get("features", [])
    for i, feature in enumerate(features):
        seq_id = feature.get("sequence_id", "")
        if seq_id and seq_id not in entry_ids:
            errors.append(ErrorDetail(
                type="invalid_sequence_id_reference",
                loc=["features", i, "sequence_id"],
                msg=f"sequence_id '{seq_id}' does not match any sequences.entries[].id",
            ))

    return errors


def validate_json_data(json_data: dict[str, Any], schema_version: str) -> ValidationResult:
    # Validate against schema
    validation_result = validate_schema(json_data, schema_version)
    if not validation_result.valid:
        return validation_result

    # Validate referential integrity
    ref_errors = _validate_referential_integrity(json_data)
    if ref_errors:
        return ValidationResult(valid=False, errors=ref_errors)

    # TODO: Validate that json_data["schema_version"] is consistent with the specified schema_version.
    #   e.g., when schema_version="v2", json_data["schema_version"] should match "v2.x" pattern.
    # TODO: Validate against INSDC feature / qualifier tables.

    return validation_result


def main() -> None:
    try:
        args = parse_args(sys.argv[1:])

        try:
            with args.input.open("r", encoding="utf-8") as f:
                json_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON file {args.input}: {e}") from e

        validation_result = validate_json_data(json_data, args.version)
        print(validation_result.model_dump_json(indent=2))

    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
