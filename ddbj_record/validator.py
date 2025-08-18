"""DDBJ Record Validator CLI.

Command-line interface for validating DDBJ record JSON files against schema specifications.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ValidationError

from ddbj_record.schema import LATEST_VERSION, SCHEMA_VERSIONS
from ddbj_record.utils import resolve_record_model


class ErrorDetail(BaseModel):
    type: str
    loc: List[str | int]
    msg: str


class ValidationResult(BaseModel):
    valid: bool
    errors: Optional[List[ErrorDetail]] = None


class Args(BaseModel):
    """Command line arguments for the validator."""
    version: str
    input: Path


def parse_args(args: Optional[list[str]] = None) -> Args:
    parser = argparse.ArgumentParser(
        description="DDBJ record - validates JSON file against specified schema version",
        epilog="Example: %(prog)s --version v1 --input sample_record.json",
    )

    parser.add_argument(
        "-v",
        "--version",
        type=str,
        default=LATEST_VERSION,
        help=f"Schema version to dump ({', '.join(SCHEMA_VERSIONS)})"
    )

    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        required=True,
        dest="json_file",
        help="Path to JSON file to validate"
    )

    if args is None:
        args = sys.argv[1:]

    parsed_args = parser.parse_args(args)
    if parsed_args.version not in SCHEMA_VERSIONS:
        parser.error(f"Invalid schema version: {parsed_args.version}. "
                     f"Supported versions are: {', '.join(SCHEMA_VERSIONS)}")
    if not parsed_args.json_file.exists():
        parser.error(f"JSON file does not exist: {parsed_args.json_file}")

    return Args(
        version=parsed_args.version,
        input=parsed_args.json_file,
    )


def validate_schema(json_data: Dict[str, Any], schema_version: str) -> ValidationResult:
    DdbjRecord = resolve_record_model(schema_version)

    try:
        DdbjRecord.model_validate(json_data)
        return ValidationResult(valid=True)
    except ValidationError as e:
        errors: List[ErrorDetail] = []
        for err in e.errors():
            error_detail = ErrorDetail(
                type=err.get("type", "validation_error"),
                loc=list(err.get("loc", [])),
                msg=err.get("msg", ""),
            )
            errors.append(error_detail)

        return ValidationResult(valid=False, errors=errors)


def main() -> None:
    try:
        args = parse_args(sys.argv[1:])

        try:
            with args.input.open("r", encoding="utf-8") as f:
                json_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON file {args.input}: {e}") from e

        # Validate against schema
        validation_result = validate_schema(json_data, args.version)
        print(validation_result.model_dump_json(indent=2))

        # TODO: Impl. validate against feature / qualifier tables

    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
