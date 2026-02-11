import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ddbj_record.schema.cli import main, parse_args

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

# === parse_args ===


def test_parse_args_valid_version() -> None:
    args = parse_args(["--version", "v2"])
    assert args.version == "v2"


def test_parse_args_v1_valid() -> None:
    args = parse_args(["--version", "v1"])
    assert args.version == "v1"


def test_parse_args_invalid_version_raises() -> None:
    with pytest.raises(SystemExit):
        parse_args(["--version", "v999"])


# === main: schema generation ===


def test_main_generates_schema_file(tmp_path: Path, mocker: "MockerFixture") -> None:
    schema_dir = tmp_path.joinpath("schemas")
    schema_dir.mkdir()
    mocker.patch("ddbj_record.schema.cli.get_schema_dir_path", return_value=schema_dir)
    mocker.patch("sys.argv", ["dump_json_schema", "--version", "v2"])
    main()
    output_path = schema_dir.joinpath("v2", "ddbj_record.schema.json")
    assert output_path.exists()
    with output_path.open("r", encoding="utf-8") as f:
        schema = json.load(f)
    assert "properties" in schema


def test_main_generates_v1_schema_file(tmp_path: Path, mocker: "MockerFixture") -> None:
    schema_dir = tmp_path.joinpath("schemas")
    schema_dir.mkdir()
    mocker.patch("ddbj_record.schema.cli.get_schema_dir_path", return_value=schema_dir)
    mocker.patch("sys.argv", ["dump_json_schema", "--version", "v1"])
    main()
    output_path = schema_dir.joinpath("v1", "ddbj_record.schema.json")
    assert output_path.exists()
