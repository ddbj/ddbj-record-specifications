import json
from pathlib import Path
from typing import Any, cast

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent.parent.joinpath("fixtures")


def _load_json(relative_path: str) -> dict[str, Any]:
    path = FIXTURES_DIR.joinpath(relative_path)
    with path.open("r", encoding="utf-8") as f:
        return cast(dict[str, Any], json.load(f))


# === v1 fixtures ===


@pytest.fixture
def v1_valid_minimal() -> dict[str, Any]:

    return _load_json("v1/valid_minimal.json")


@pytest.fixture
def v1_valid_dfc_gnm() -> dict[str, Any]:

    return _load_json("v1/valid_dfc_gnm.json")


@pytest.fixture
def v1_valid_wf_dfc_wgs() -> dict[str, Any]:

    return _load_json("v1/valid_wf_dfc_wgs.json")


@pytest.fixture
def v1_valid_wgs_with_keyword() -> dict[str, Any]:

    return _load_json("v1/valid_wgs_with_keyword.json")


@pytest.fixture
def v1_invalid_missing_required() -> dict[str, Any]:

    return _load_json("v1/invalid_missing_required.json")


@pytest.fixture
def v1_invalid_wrong_type() -> dict[str, Any]:

    return _load_json("v1/invalid_wrong_type.json")


@pytest.fixture
def v1_legacy_schema_version() -> dict[str, Any]:

    return _load_json("v1/legacy_schema_version.json")


# === v2 fixtures ===


@pytest.fixture
def v2_valid_minimal() -> dict[str, Any]:

    return _load_json("v2/valid_minimal.json")


@pytest.fixture
def v2_valid_dfc_gnm() -> dict[str, Any]:

    return _load_json("v2/valid_dfc_gnm.json")


@pytest.fixture
def v2_valid_wf_dfc_wgs() -> dict[str, Any]:

    return _load_json("v2/valid_wf_dfc_wgs.json")


@pytest.fixture
def v2_valid_dfv() -> dict[str, Any]:

    return _load_json("v2/valid_dfv.json")


@pytest.fixture
def v2_valid_wf_dfv() -> dict[str, Any]:

    return _load_json("v2/valid_wf_dfv.json")


@pytest.fixture
def v2_valid_boolean_qualifier() -> dict[str, Any]:

    return _load_json("v2/valid_boolean_qualifier.json")


@pytest.fixture
def v2_valid_complex_location() -> dict[str, Any]:

    return _load_json("v2/valid_complex_location.json")


@pytest.fixture
def v2_valid_multi_source() -> dict[str, Any]:

    return _load_json("v2/valid_multi_source.json")


@pytest.fixture
def v2_valid_wgs_with_keyword() -> dict[str, Any]:

    return _load_json("v2/valid_wgs_with_keyword.json")


@pytest.fixture
def v2_invalid_missing_required() -> dict[str, Any]:

    return _load_json("v2/invalid_missing_required.json")


@pytest.fixture
def v2_invalid_wrong_type() -> dict[str, Any]:

    return _load_json("v2/invalid_wrong_type.json")


@pytest.fixture
def v2_invalid_extra_field() -> dict[str, Any]:

    return _load_json("v2/invalid_extra_field.json")


@pytest.fixture
def v2_legacy_schema_version() -> dict[str, Any]:

    return _load_json("v2/legacy_schema_version.json")


# === converter fixtures ===


@pytest.fixture
def v1_to_v2_input() -> dict[str, Any]:

    return _load_json("converter/v1_to_v2_input.json")


@pytest.fixture
def v1_to_v2_expected() -> dict[str, Any]:

    return _load_json("converter/v1_to_v2_expected.json")


@pytest.fixture
def v2_to_v1_input() -> dict[str, Any]:

    return _load_json("converter/v2_to_v1_input.json")


@pytest.fixture
def v2_to_v1_expected() -> dict[str, Any]:

    return _load_json("converter/v2_to_v1_expected.json")
