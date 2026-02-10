from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, cast

import jsonref  # type: ignore[import-untyped]
from pydantic import BaseModel
from pydantic.json_schema import JsonSchemaValue


def get_root_path() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if parent.joinpath("pyproject.toml").exists():
            return parent

    raise FileNotFoundError("pyproject.toml not found in any parent directories.")


def get_schema_dir_path() -> Path:
    return get_root_path().joinpath("schemas")


def deref_schema(schema: JsonSchemaValue) -> JsonSchemaValue:
    """
    Dereference a JSON schema by resolving $ref references.
    """
    resolved_schema = jsonref.loads(json.dumps(schema))
    resolved_schema_dict = dict(resolved_schema)
    del resolved_schema_dict["$defs"]
    return resolved_schema_dict


def resolve_record_model(version: str) -> type[BaseModel]:
    try:
        module = importlib.import_module(f"ddbj_record.schema.{version}")
    except ImportError as e:
        raise ImportError(f"Failed to import schema module for version {version}: {e}") from e

    try:
        model: Any = module.DdbjRecord
    except AttributeError as e:
        raise AttributeError(f"Module {version} does not contain DdbjRecord model: {e}") from e

    if not issubclass(model, BaseModel):
        raise TypeError(f"DdbjRecord in {version} must be a subclass of Pydantic BaseModel")

    return cast("type[BaseModel]", model)
