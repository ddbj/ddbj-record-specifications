import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from ddbj_record.converter.cli import convert_json_data, parse_args

# === parse_args ===


def test_parse_args_valid_arguments(tmp_path: Path) -> None:
    input_file = tmp_path.joinpath("input.json")
    input_file.write_text("{}")
    output_file = tmp_path.joinpath("output.json")
    args = parse_args(["--from", "v1", "--to", "v2", "--input", str(input_file), "--output", str(output_file)])
    assert args.from_ == "v1"
    assert args.to == "v2"


def test_parse_args_minor_version_normalized_to_major(tmp_path: Path) -> None:
    input_file = tmp_path.joinpath("input.json")
    input_file.write_text("{}")
    output_file = tmp_path.joinpath("output.json")
    args = parse_args(["--from", "v1.0", "--to", "v2.0", "--input", str(input_file), "--output", str(output_file)])
    assert args.from_ == "v1"
    assert args.to == "v2"


def test_parse_args_invalid_from_version_raises(tmp_path: Path) -> None:
    input_file = tmp_path.joinpath("input.json")
    input_file.write_text("{}")
    with pytest.raises(SystemExit):
        parse_args(["--from", "v999", "--to", "v2", "--input", str(input_file), "--output", "out.json"])


def test_parse_args_invalid_to_version_raises(tmp_path: Path) -> None:
    input_file = tmp_path.joinpath("input.json")
    input_file.write_text("{}")
    with pytest.raises(SystemExit):
        parse_args(["--from", "v1", "--to", "v999", "--input", str(input_file), "--output", "out.json"])


def test_parse_args_nonexistent_input_raises() -> None:
    with pytest.raises(SystemExit):
        parse_args(["--from", "v1", "--to", "v2", "--input", "/nonexistent.json", "--output", "out.json"])


# === convert_json_data ===


def test_convert_json_data_same_version_v1_identity(v1_valid_minimal: dict[str, Any]) -> None:
    result = convert_json_data(v1_valid_minimal, "v1", "v1")
    assert result == v1_valid_minimal


def test_convert_json_data_same_version_v2_identity(v2_valid_minimal: dict[str, Any]) -> None:
    result = convert_json_data(v2_valid_minimal, "v2", "v2")
    assert result == v2_valid_minimal


def test_convert_json_data_v1_to_v2(v1_to_v2_input: dict[str, Any]) -> None:
    result = convert_json_data(v1_to_v2_input, "v1", "v2")
    assert result["schema_version"] == "v2.0"
    assert "provenance" in result
    assert "submission" in result


def test_convert_json_data_v2_to_v1(v2_to_v1_input: dict[str, Any]) -> None:
    result = convert_json_data(v2_to_v1_input, "v2", "v1")
    assert result["schema_version"] == "v1.0"
    assert "COMMON" in result


def test_convert_json_data_unsupported_pair_raises(v1_valid_minimal: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="Unsupported conversion"):
        convert_json_data(v1_valid_minimal, "v1", "draft")


# === post-conversion validation ===


def test_converter_cli_runs_post_conversion_validation(
    tmp_path: Path,
    v1_to_v2_input: dict[str, Any],
) -> None:
    input_file = tmp_path.joinpath("input.json")
    output_file = tmp_path.joinpath("output.json")
    input_file.write_text(json.dumps(v1_to_v2_input))
    result = subprocess.run(
        [
            "uv",
            "run",
            "ddbj_record_converter",
            "--from",
            "v1",
            "--to",
            "v2",
            "--input",
            str(input_file),
            "--output",
            str(output_file),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert output_file.exists()
    output_data = json.loads(output_file.read_text())
    assert output_data["schema_version"] == "v2.0"
