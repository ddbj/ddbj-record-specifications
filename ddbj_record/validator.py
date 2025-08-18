"""DDBJ Record Validator CLI.

Command-line interface for validating DDBJ record JSON files against schema specifications.
Supports both v1 and v2 schema versions with detailed error reporting.
"""

import argparse
import json
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, ValidationError

from ddbj_record.schema.v1 import DdbjRecord as DdbjRecordV1
from ddbj_record.schema.v2 import DdbjRecord as DdbjRecordV2


class SchemaVersion(str, Enum):
    """Supported DDBJ record schema versions."""

    V1 = "v1"
    V2 = "v2"


class Args(BaseModel):
    """Command line arguments for the validator."""

    schema_version: SchemaVersion
    json_file: Path


def parse_args(args: Optional[list[str]] = None) -> Args:
    """Parse and validate command line arguments.

    Args:
        args: Optional list of arguments for testing purposes

    Returns:
        Validated arguments

    Raises:
        SystemExit: If argument parsing fails
    """
    parser = argparse.ArgumentParser(
        description="DDBJ record validator - validates JSON records against specified schema version",
        epilog="Example: %(prog)s v1 --json sample_record.json",
    )

    parser.add_argument(
        "schema_version",
        choices=[v.value for v in SchemaVersion],
        help=f"Schema version to validate against ({', '.join([v.value for v in SchemaVersion])})"
    )
    parser.add_argument(
        "--json",
        type=Path,
        required=True,
        dest="json_file",
        help="Path to JSON file to validate"
    )

    if args is None:
        args = sys.argv[1:]

    try:
        parsed_args = parser.parse_args(args)
        return Args(
            schema_version=SchemaVersion(parsed_args.schema_version),
            json_file=parsed_args.json_file
        )
    except Exception as e:
        print(f"Error parsing arguments: {e}", file=sys.stderr)
        sys.exit(1)


def validate_json_data(json_data: Dict[str, Any], schema_version: SchemaVersion) -> None:
    """Validate JSON data against the specified schema version.

    Args:
        json_data: Parsed JSON data to validate
        schema_version: Schema version to validate against

    Raises:
        ValidationError: If validation fails
        ValueError: If unsupported schema version is provided
    """
    try:
        if schema_version == SchemaVersion.V1:
            DdbjRecordV1(**json_data)
        elif schema_version == SchemaVersion.V2:
            DdbjRecordV2(**json_data)
        else:
            raise ValueError(f"Unsupported schema version: {schema_version}")

        print(f"✓ Validation successful using schema {schema_version.value}")

    except ValidationError as e:
        print(f"✗ Validation failed using schema {schema_version.value}:", file=sys.stderr)
        print(e, file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main entry point for the validator CLI."""
    try:
        args = parse_args()

        # Check if file exists
        if not args.json_file.exists():
            print(f"Error: File {args.json_file} does not exist", file=sys.stderr)
            sys.exit(1)

        # Load and parse JSON
        try:
            with args.json_file.open("r", encoding="utf-8") as f:
                json_data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON format in {args.json_file}: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error reading file {args.json_file}: {e}", file=sys.stderr)
            sys.exit(1)

        # Validate against schema
        validate_json_data(json_data, args.schema_version)

    except KeyboardInterrupt:
        print("\nOperation cancelled by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
