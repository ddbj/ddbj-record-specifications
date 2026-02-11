"""INSDC feature/qualifier definition loader."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from ddbj_record.insdc.models import InsdcDefinition

_YAML_PATH = Path(__file__).resolve().parent.joinpath("insdc_feature_table.yaml")


@lru_cache(maxsize=1)
def load_insdc_definition() -> InsdcDefinition:
    with _YAML_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return InsdcDefinition.model_validate(data)
