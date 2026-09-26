import pytest
from pydantic import BaseModel

from ddbj_record.utils import resolve_record_model

# === resolve_record_model ===


def test_resolve_record_model_v1_returns_correct_model() -> None:
    model = resolve_record_model("v1")
    assert issubclass(model, BaseModel)
    assert model.__name__ == "DdbjRecord"


def test_resolve_record_model_v2_returns_correct_model() -> None:
    model = resolve_record_model("v2")
    assert issubclass(model, BaseModel)
    assert model.__name__ == "DdbjRecord"


def test_resolve_record_model_v3_returns_correct_model() -> None:
    model = resolve_record_model("v3")
    assert issubclass(model, BaseModel)
    assert model.__name__ == "DdbjRecord"


def test_resolve_record_model_v1_v2_are_different() -> None:
    v1_model = resolve_record_model("v1")
    v2_model = resolve_record_model("v2")
    assert v1_model is not v2_model


def test_resolve_record_model_invalid_version_raises() -> None:
    with pytest.raises(ImportError, match="Failed to import schema module"):
        resolve_record_model("v999")
