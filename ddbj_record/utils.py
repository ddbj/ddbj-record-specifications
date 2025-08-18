import json
from pathlib import Path

import jsonref  # type: ignore[import-untyped]
from pydantic.json_schema import JsonSchemaValue


def get_root_path() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if parent.joinpath("pyproject.toml").exists():
            return parent

    raise FileNotFoundError("pyproject.toml not found in any parent directories.")


def get_schema_dir_path() -> Path:
    return get_root_path().joinpath("schemas")


def get_feature_table_dir_path() -> Path:
    return get_root_path().joinpath("feature_table")


def deref_schema(schema: JsonSchemaValue) -> JsonSchemaValue:
    """
    Dereference a JSON schema by resolving $ref references.
    """
    resolved_schema = jsonref.loads(json.dumps(schema))
    resolved_schema_dict = dict(resolved_schema)
    del resolved_schema_dict["$defs"]
    return resolved_schema_dict
