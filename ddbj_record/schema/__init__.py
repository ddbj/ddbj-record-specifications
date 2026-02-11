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
    "v2": "v2.1",
}

# Deprecated schema_version values.
# Maintained for backward compatibility during the transition to v{major}.{minor} format.
# New data should use "v1.0", "v2.0", etc.
LEGACY_SCHEMA_VERSION_MAP = {
    "0.1": "v1.0",
    "v1": "v1.0",
    "0.2": "v2.0",
    "v2": "v2.0",
}


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
