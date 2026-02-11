import pytest

from ddbj_record.schema import (
    LATEST_MINOR_VERSIONS,
    LATEST_VERSION,
    LEGACY_SCHEMA_VERSION_MAP,
    SCHEMA_VERSIONS,
    normalize_cli_version,
)


def test_schema_versions_contains_v1() -> None:
    assert "v1" in SCHEMA_VERSIONS


def test_schema_versions_contains_v2() -> None:
    assert "v2" in SCHEMA_VERSIONS


def test_schema_versions_contains_draft() -> None:
    assert "draft" in SCHEMA_VERSIONS


def test_latest_version_is_v2() -> None:
    assert LATEST_VERSION == "v2"


def test_legacy_map_01_to_v10() -> None:
    assert LEGACY_SCHEMA_VERSION_MAP["0.1"] == "v1.0"


def test_legacy_map_v1_to_v10() -> None:
    assert LEGACY_SCHEMA_VERSION_MAP["v1"] == "v1.0"


def test_legacy_map_02_to_v20() -> None:
    assert LEGACY_SCHEMA_VERSION_MAP["0.2"] == "v2.0"


# === LATEST_MINOR_VERSIONS ===


def test_latest_minor_versions_v1() -> None:
    assert LATEST_MINOR_VERSIONS["v1"] == "v1.0"


def test_latest_minor_versions_v2() -> None:
    assert LATEST_MINOR_VERSIONS["v2"] == "v2.0"


# === normalize_cli_version ===


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("v1", "v1"),
        ("v2", "v2"),
        ("draft", "draft"),
        ("v1.0", "v1"),
        ("v2.0", "v2"),
        ("v2.1", "v2"),
        ("v1.99", "v1"),
    ],
)
def test_normalize_cli_version_valid(raw: str, expected: str) -> None:
    assert normalize_cli_version(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "v999",
        "v3.0",
        "0.1",
        "0.2",
        "invalid",
        "",
        "v",
        "v2.",
    ],
)
def test_normalize_cli_version_invalid_returns_none(raw: str) -> None:
    assert normalize_cli_version(raw) is None
