import pytest
from pydantic import BaseModel

from ddbj_record.utils import deref_schema, get_root_path, resolve_record_model

# === resolve_record_model ===


def test_resolve_record_model_v1_returns_correct_model() -> None:
    model = resolve_record_model("v1")
    assert issubclass(model, BaseModel)
    assert model.__name__ == "DdbjRecord"


def test_resolve_record_model_v2_returns_correct_model() -> None:
    model = resolve_record_model("v2")
    assert issubclass(model, BaseModel)
    assert model.__name__ == "DdbjRecord"


def test_resolve_record_model_v1_v2_are_different() -> None:
    v1_model = resolve_record_model("v1")
    v2_model = resolve_record_model("v2")
    assert v1_model is not v2_model


def test_resolve_record_model_invalid_version_raises() -> None:
    with pytest.raises(ImportError, match="Failed to import schema module"):
        resolve_record_model("v999")


# === get_root_path ===


def test_get_root_path_contains_pyproject_toml() -> None:
    root = get_root_path()
    assert root.joinpath("pyproject.toml").exists()


def test_get_root_path_is_directory() -> None:
    root = get_root_path()
    assert root.is_dir()


# === deref_schema ===


def test_deref_schema_resolves_refs() -> None:
    schema = {
        "$defs": {
            "Inner": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
            }
        },
        "type": "object",
        "properties": {
            "inner": {"$ref": "#/$defs/Inner"},
        },
    }
    result = deref_schema(schema)
    assert "$defs" not in result
    assert result["properties"]["inner"]["type"] == "object"


def test_deref_schema_removes_defs_key() -> None:
    model = resolve_record_model("v2")
    schema = model.model_json_schema()
    result = deref_schema(schema)
    assert "$defs" not in result
    assert "properties" in result
