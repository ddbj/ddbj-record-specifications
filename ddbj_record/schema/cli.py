from __future__ import annotations

import argparse
import json
import sys

from pydantic import BaseModel

from ddbj_record.schema import SCHEMA_VERSIONS, normalize_cli_version
from ddbj_record.utils import deref_schema, get_schema_dir_path, resolve_record_model


class Args(BaseModel):
    version: str


def parse_args(args: list[str] | None = None) -> Args:
    parser = argparse.ArgumentParser(
        description="DDBJ Record - dump JSON schema from pydantic models",
        epilog="Example: %(prog)s --version v2",
    )

    parser.add_argument(
        "-v", "--version", type=str, required=True, help=f"Schema version to dump ({', '.join(SCHEMA_VERSIONS)})"
    )

    if args is None:
        args = sys.argv[1:]

    parsed_args = parser.parse_args(args)
    normalized_version = normalize_cli_version(parsed_args.version)
    if normalized_version is None:
        parser.error(
            f"Invalid schema version: {parsed_args.version}. Supported versions are: {', '.join(SCHEMA_VERSIONS)}"
        )

    return Args(
        version=normalized_version,
    )


def main() -> None:
    try:
        args = parse_args(sys.argv[1:])
        print(f"Dumping schema for version: {args.version}")

        record_model = resolve_record_model(args.version)

        schema_dir_path = get_schema_dir_path()
        schema_path = schema_dir_path.joinpath(f"{args.version}/ddbj_record.schema.json")
        schema_path.parent.mkdir(parents=True, exist_ok=True)

        schema_dict = record_model.model_json_schema()
        resolved_schema_dict = deref_schema(schema_dict)

        with schema_path.open("w", encoding="utf-8") as f:
            f.write(json.dumps(resolved_schema_dict, indent=2))

        print(f"Wrote schema to: {schema_path}")

    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
