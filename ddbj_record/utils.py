from __future__ import annotations

import importlib
from typing import Any, cast

from pydantic import BaseModel


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
