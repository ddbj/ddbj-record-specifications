"""DDBJ Record Converter

Command-line interface for converting DDBJ record JSON files between different schema versions.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel

from ddbj_record.converter.v1_to_v2 import v1_to_v2
from ddbj_record.converter.v2_to_v1 import v2_to_v1
from ddbj_record.schema import SCHEMA_VERSIONS
from ddbj_record.utils import resolve_record_model
from ddbj_record.validator import validate_json_data


class Args(BaseModel):
    """Command line arguments for the validator."""
    from_: str
    to: str
    input: Path
    output: Path


def parse_args(args: Optional[list[str]] = None) -> Args:
    parser = argparse.ArgumentParser(
        description="DDBJ Record Converter - converts JSON records between schema versions",
        epilog="Example: %(prog)s --from v1 --to v2 --input sample_record_v1.json --output sample_record_v2.json",
    )

    parser.add_argument(
        "--from",
        type=str,
        required=True,
        help="Schema version to convert from. If not specified, the version will be inferred from the input file.",
        dest="from_",
    )
    parser.add_argument(
        "--to",
        type=str,
        required=True,
        help="Schema version to convert to (e.g., 'v1' or 'v2')"
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        required=True,
        help="Path to the input JSON file to convert"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="Path to save the converted JSON file"
    )

    if args is None:
        args = sys.argv[1:]

    parsed_args = parser.parse_args(args)
    if parsed_args.from_ not in SCHEMA_VERSIONS:
        parser.error(f"Invalid schema version for 'from': {parsed_args.from_}. "
                     f"Supported versions are: {', '.join(SCHEMA_VERSIONS)}")
    if parsed_args.to not in SCHEMA_VERSIONS:
        parser.error(f"Invalid schema version for 'to': {parsed_args.to}. "
                     f"Supported versions are: {', '.join(SCHEMA_VERSIONS)}")
    if not parsed_args.input.exists():
        parser.error(f"Input JSON file does not exist: {parsed_args.input}")

    return Args(
        from_=parsed_args.from_,
        to=parsed_args.to,
        input=parsed_args.input,
        output=parsed_args.output
    )


def convert_json_data(json_data: Dict[str, Any], from_: str, to: str) -> Dict[str, Any]:
    # TODO: 敢えて愚直に converter の選択を書いている
    # もう少しかっこよく出来る気もしているが、増えてきてから考える
    # schema の class に変換系の method を持たせるのは可読性が落ちそうなため、やめておく

    FromDdbjRecord = resolve_record_model(from_)

    if from_ == "v1" and to == "v1":
        return json_data
    elif from_ == "v1" and to == "v2":
        v1_obj = FromDdbjRecord.model_validate(json_data)
        return v1_to_v2(v1_obj).model_dump(exclude_none=True, by_alias=True)  # type: ignore
    elif from_ == "v2" and to == "v1":
        v2_obj = FromDdbjRecord.model_validate(json_data)
        return v2_to_v1(v2_obj).model_dump(exclude_none=True, by_alias=True)  # type: ignore
    elif from_ == "v2" and to == "v2":
        return json_data
    else:
        raise ValueError(f"Unsupported conversion from {from_} to {to}")


def main() -> None:
    try:
        args = parse_args(sys.argv[1:])

        try:
            with args.input.open("r", encoding="utf-8") as f:
                input_json_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON file {args.input}: {e}") from e

        validation_result = validate_json_data(input_json_data, args.from_)
        if not validation_result.valid:
            print(f"Validation failed for input file {args.input} using schema {args.from_}. "
                  f"Errors: {validation_result.errors}", file=sys.stderr)
            sys.exit(1)

        converted_data = convert_json_data(input_json_data, args.from_, args.to)
        with args.output.open("w", encoding="utf-8") as f:
            json.dump(converted_data, f, indent=2, ensure_ascii=False)

    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
