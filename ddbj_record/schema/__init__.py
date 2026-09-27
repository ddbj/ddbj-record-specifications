from __future__ import annotations

import re

SCHEMA_VERSIONS = [
    "v1",
    "v2",
    "v3",
]

# The minor each major's types are at, which is what a record written with them states in
# schema_version. It is raised whenever the major's shape changes (docs/versioning.md).
LATEST_MINOR_VERSIONS: dict[str, str] = {
    "v1": "v1.0",
    "v2": "v2.3",
    "v3": "v3.1",
}

# Majors whose types read every minor as the latest one. From v3 on, a minor may change the
# shape, so a record keeps the minor it was written in.
_FOLDED_MAJORS = ("v1", "v2")

# Mapping from legacy schema_version values to their major version.
_LEGACY_TO_MAJOR: dict[str, str] = {
    "0.1": "v1",
    "v1": "v1",
    "0.2": "v2",
    "v2": "v2",
}


def normalize_schema_version(raw: str) -> str | None:
    """Normalize a v1 / v2 schema_version value to the latest minor version.

    Accepts legacy values ("0.1", "v1", "0.2", "v2") and canonical values
    ("v1.0", "v2.0", "v2.1") and returns the latest minor version for that
    major version (e.g., "v2.3"). Returns None if the input is unrecognized,
    which includes every v3 value: a v3 record keeps the minor it was written in.
    """
    if raw in _LEGACY_TO_MAJOR:
        major = _LEGACY_TO_MAJOR[raw]
        return LATEST_MINOR_VERSIONS.get(major)
    match = re.fullmatch(r"(v\d+)\.\d+", raw)
    if match and match.group(1) in _FOLDED_MAJORS:
        return LATEST_MINOR_VERSIONS[match.group(1)]
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
