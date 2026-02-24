from __future__ import annotations

import re

SCHEMA_VERSIONS = [
    "v1",
    "v2",
    "draft",
]
LATEST_VERSION = "v2"

# Latest minor version for each major version.
# Used by converters to set schema_version in output data.
LATEST_MINOR_VERSIONS: dict[str, str] = {
    "v1": "v1.0",
    "v2": "v2.2",
}

# Mapping from legacy schema_version values to their major version.
_LEGACY_TO_MAJOR: dict[str, str] = {
    "0.1": "v1",
    "v1": "v1",
    "0.2": "v2",
    "v2": "v2",
}


def normalize_schema_version(raw: str) -> str | None:
    """Normalize a schema_version value to the latest minor version.

    Accepts legacy values ("0.1", "v1", "0.2", "v2") and canonical values
    ("v1.0", "v2.0", "v2.1") and returns the latest minor version for that
    major version (e.g., "v2.1"). Returns None if the input is unrecognized.
    """
    if raw in _LEGACY_TO_MAJOR:
        major = _LEGACY_TO_MAJOR[raw]
        return LATEST_MINOR_VERSIONS.get(major)
    match = re.fullmatch(r"(v\d+)\.\d+", raw)
    if match:
        major = match.group(1)
        return LATEST_MINOR_VERSIONS.get(major)
    return None


def normalize_cli_version(raw: str) -> str | None:
    """Normalize a CLI version argument to a major version string.

    Accepts "v1", "v2", "v1.0", "v2.1", etc. and returns the major version
    ("v1", "v2"). Returns None if the input does not match any known pattern.
    """
    if raw in SCHEMA_VERSIONS:
        return raw
    match = re.fullmatch(r"(v\d+)\.\d+", raw)
    if match and match.group(1) in SCHEMA_VERSIONS:
        return match.group(1)
    return None
