SCHEMA_VERSIONS = [
    "v1",
    "v2",
    "draft",
]
LATEST_VERSION = "v2"

# Deprecated schema_version values.
# Maintained for backward compatibility during the transition to v{major}.{minor} format.
# New data should use "v1.0", "v2.0", etc.
LEGACY_SCHEMA_VERSION_MAP = {
    "0.1": "v1.0",
    "v1": "v1.0",
    "0.2": "v2.0",
    "v2": "v2.0",
}
