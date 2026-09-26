"""DDBJ Record JSON Schema dumper

Writes the JSON Schema of a major version's DdbjRecord to stdout.
"""

from __future__ import annotations

import argparse
import json
import sys

from pydantic import BaseModel

from ddbj_record.schema import SCHEMA_VERSIONS, normalize_cli_version
from ddbj_record.utils import resolve_record_model


class Args(BaseModel):
    version: str


def parse_args(args: list[str] | None = None) -> Args:
    parser = argparse.ArgumentParser(
        description="DDBJ Record - write the JSON Schema of a major version to stdout",
        epilog="Example: %(prog)s --version v3 > ddbj_record.schema.json",
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

    return Args(version=normalized_version)


def dump_schema(version: str) -> str:
    return json.dumps(resolve_record_model(version).model_json_schema(), indent=2, ensure_ascii=False)


def main() -> None:
    args = parse_args(sys.argv[1:])
    sys.stdout.write(dump_schema(args.version) + "\n")


if __name__ == "__main__":
    main()
