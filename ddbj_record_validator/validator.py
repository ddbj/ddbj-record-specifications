import argparse
import json
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel

from ddbj_record_validator.schema.v1 import DdbjRecord as DdbjRecordV1
from ddbj_record_validator.schema.v2 import DdbjRecord as DdbjRecordV2


class SchemaVersion(str, Enum):
    V1 = "v1"
    V2 = "v2"


class Args(BaseModel):
    schema_version: SchemaVersion
    json_file: Path


def parse_args(args: Optional[list[str]] = None) -> Args:
    parser = argparse.ArgumentParser(
        description="DDBJ record validator - validates JSON records against specified schema version",
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

    parsed_args = parser.parse_args(args)
    return Args(
        schema_version=SchemaVersion(parsed_args.schema_version),
        json_file=parsed_args.json_file
    )


def validate_json_data(json_data: Dict[str, Any], schema_version: SchemaVersion) -> None:
    try:
        if schema_version == SchemaVersion.V1:
            DdbjRecordV1(**json_data)
        elif schema_version == SchemaVersion.V2:
            DdbjRecordV2(**json_data)
        else:
            raise ValueError(f"Unsupported schema version: {schema_version}")

        print(f"Validation successful using schema {schema_version.value}")

    except Exception as e:
        print(f"Validation failed using schema {schema_version.value}:", file=sys.stderr)
        print(e, file=sys.stderr)
        sys.exit(1)


def main() -> None:
    args = parse_args()

    if not args.json_file.exists():
        print(f"Error: JSON file '{args.json_file}' does not exist.", file=sys.stderr)
        sys.exit(1)
    with args.json_file.open("r", encoding="utf-8") as f:
        json_data = json.load(f)

    validate_json_data(json_data, args.schema_version)


if __name__ == "__main__":
    main()
