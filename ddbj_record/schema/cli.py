import argparse
import importlib
import json
import sys
from typing import Optional, Type

import jsonref  # type: ignore[import-untyped]
from pydantic import BaseModel

from ddbj_record.schema import SCHEMA_VERSIONS
from ddbj_record.utils import get_schema_dir_path


class Args(BaseModel):
    version: str


def parse_args(args: Optional[list[str]] = None) -> Args:
    parser = argparse.ArgumentParser(
        description="DDBJ Record - dump JSON schema from pydantic models",
        epilog="Example: %(prog)s --version v2",
    )

    parser.add_argument(
        "-v",
        "--version",
        type=str,
        required=True,
        help=f"Schema version to dump ({', '.join(SCHEMA_VERSIONS)})"
    )

    if args is None:
        args = sys.argv[1:]

    parsed_args = parser.parse_args(args)
    if parsed_args.version not in SCHEMA_VERSIONS:
        parser.error(f"Invalid schema version: {parsed_args.version}. "
                     f"Supported versions are: {', '.join(SCHEMA_VERSIONS)}")

    return Args(
        version=parsed_args.version,
    )


def resolve_record_model(version: str) -> Type[BaseModel]:
    try:
        module = importlib.import_module(f"ddbj_record.schema.{version}")
    except ImportError as e:
        raise Exception(f"Failed to import schema module for version {version}: {e}") from e

    try:
        model = getattr(module, "DdbjRecord")
    except AttributeError as e:
        raise Exception(f"Module {version} does not contain DdbjRecord model: {e}") from e

    if not issubclass(model, BaseModel):
        raise TypeError(f"DdbjRecord in {version} must be a subclass of Pydantic BaseModel")

    return model  # type: ignore


def main() -> None:
    args = parse_args(sys.argv[1:])
    print(f"Dumping schema for version: {args.version}")

    DdbjRecord = resolve_record_model(args.version)

    schema_dir_path = get_schema_dir_path()
    schema_path = schema_dir_path.joinpath(f"{args.version}/ddbj_record.schema.json")
    schema_path.parent.mkdir(parents=True, exist_ok=True)

    schema_dict = DdbjRecord.model_json_schema()
    resolved_schema = jsonref.loads(json.dumps(schema_dict))
    resolved_schema_dict = dict(resolved_schema)
    del resolved_schema_dict["$defs"]

    with schema_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(resolved_schema_dict, indent=2))

    print(f"Wrote schema to: {schema_path}")


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
