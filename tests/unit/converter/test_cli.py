import json
import subprocess
import sys
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
    assert result["schema_version"] == "v2.3"
    assert "provenance" in result
    assert "submission" in result


def test_convert_json_data_v2_to_v1(v2_to_v1_input: dict[str, Any]) -> None:
    result = convert_json_data(v2_to_v1_input, "v2", "v1")
    assert result["schema_version"] == "v1.0"
    assert "COMMON" in result


def test_convert_json_data_v2_to_v3(v2_to_v3_input: dict[str, Any], v2_to_v3_expected: dict[str, Any]) -> None:
    result = convert_json_data(v2_to_v3_input, "v2", "v3")
    assert result == v2_to_v3_expected


def test_convert_json_data_v1_to_v3_goes_through_v2(v1_to_v2_input: dict[str, Any]) -> None:
    result = convert_json_data(v1_to_v2_input, "v1", "v3")
    assert result == convert_json_data(convert_json_data(v1_to_v2_input, "v1", "v2"), "v2", "v3")
    assert result["schema_version"] == "v3"


def test_convert_json_data_same_version_v3_identity(v3_bioproject_other: dict[str, Any]) -> None:
    result = convert_json_data(v3_bioproject_other, "v3", "v3")
    assert result == v3_bioproject_other


@pytest.mark.parametrize("to", ["v1", "v2"])
def test_convert_json_data_from_v3_raises(v3_bioproject_other: dict[str, Any], to: str) -> None:
    # v3 から古い major への converter は無い。
    with pytest.raises(ValueError, match="Unsupported conversion"):
        convert_json_data(v3_bioproject_other, "v3", to)


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
            sys.executable,
            "-m",
            "ddbj_record.converter.cli",
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
    assert output_data["schema_version"] == "v2.3"


def test_converter_cli_v2_to_v1_subprocess(
    tmp_path: Path,
    v2_to_v1_input: dict[str, Any],
) -> None:
    input_file = tmp_path.joinpath("input.json")
    output_file = tmp_path.joinpath("output.json")
    input_file.write_text(json.dumps(v2_to_v1_input))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ddbj_record.converter.cli",
            "--from",
            "v2",
            "--to",
            "v1",
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
    assert output_data["schema_version"] == "v1.0"
    assert "COMMON" in output_data


def test_converter_cli_v2_to_v3_subprocess(
    tmp_path: Path,
    v2_to_v3_input: dict[str, Any],
    v2_to_v3_expected: dict[str, Any],
) -> None:
    input_file = tmp_path.joinpath("input.json")
    output_file = tmp_path.joinpath("output.json")
    input_file.write_text(json.dumps(v2_to_v3_input))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ddbj_record.converter.cli",
            "--from",
            "v2",
            "--to",
            "v3",
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
    assert json.loads(output_file.read_text()) == v2_to_v3_expected


def test_converter_cli_invalid_input_returns_exit_1(tmp_path: Path) -> None:
    input_file = tmp_path.joinpath("input.json")
    output_file = tmp_path.joinpath("output.json")
    input_file.write_text('{"invalid": "data"}')
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ddbj_record.converter.cli",
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
    assert result.returncode == 1
