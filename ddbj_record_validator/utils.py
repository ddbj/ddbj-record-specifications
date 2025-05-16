from pathlib import Path


def get_root_path() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if parent.joinpath("pyproject.toml").exists():
            return parent

    raise FileNotFoundError("pyproject.toml not found in any parent directories.")


def get_schema_dir_path() -> Path:
    return get_root_path().joinpath("schemas")


def get_feature_table_dir_path() -> Path:
    return get_root_path().joinpath("feature_table")
