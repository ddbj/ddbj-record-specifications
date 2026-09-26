"""DDBJ Record Converter

Command-line interface for converting DDBJ record JSON files between different schema versions.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel

from ddbj_record.converter.v1_to_v2 import v1_to_v2
from ddbj_record.converter.v2_to_v1 import v2_to_v1
from ddbj_record.schema import SCHEMA_VERSIONS, normalize_cli_version
from ddbj_record.schema.v1 import DdbjRecord as DdbjRecordV1
from ddbj_record.schema.v2 import DdbjRecord as DdbjRecordV2
from ddbj_record.utils import resolve_record_model

# v4 の record は 1 つの JSON ではなく zip のパッケージなので、ここでは扱わない。
PACKAGE_VERSIONS = frozenset({"v4"})
PACKAGE_MESSAGE = "a v4 record is a package, not a JSON file; use ddbj_record_package (pack / unpack / check)"


class Args(BaseModel):
    """Command line arguments for the converter."""

    from_: str
    to: str
    input: Path
    output: Path


def parse_args(args: list[str] | None = None) -> Args:
    parser = argparse.ArgumentParser(
        description="DDBJ Record Converter - converts JSON records between schema versions",
        epilog="Example: %(prog)s --from v1 --to v2 --input sample_record_v1.json --output sample_record_v2.json",
    )

    parser.add_argument(
        "--from",
        type=str,
        required=True,
        help="Schema version to convert from (e.g., 'v1' or 'v2')",
        dest="from_",
    )
    parser.add_argument("--to", type=str, required=True, help="Schema version to convert to (e.g., 'v1' or 'v2')")
    parser.add_argument("-i", "--input", type=Path, required=True, help="Path to the input JSON file to convert")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Path to save the converted JSON file")

    if args is None:
        args = sys.argv[1:]

    parsed_args = parser.parse_args(args)
    normalized_from = normalize_cli_version(parsed_args.from_)
    if normalized_from is None:
        parser.error(
            f"Invalid schema version for 'from': {parsed_args.from_}. "
            f"Supported versions are: {', '.join(SCHEMA_VERSIONS)}"
        )
    normalized_to = normalize_cli_version(parsed_args.to)
    if normalized_to is None:
        parser.error(
            f"Invalid schema version for 'to': {parsed_args.to}. Supported versions are: {', '.join(SCHEMA_VERSIONS)}"
        )
    # 入力を読む前に断る。v4 のパッケージを JSON として読むと、分かりにくい誤りになる。
    if PACKAGE_VERSIONS & {normalized_from, normalized_to}:
        parser.error(PACKAGE_MESSAGE)
    if not parsed_args.input.exists():
        parser.error(f"Input JSON file does not exist: {parsed_args.input}")

    return Args(from_=normalized_from, to=normalized_to, input=parsed_args.input, output=parsed_args.output)


def convert_json_data(json_data: dict[str, Any], from_: str, to: str) -> dict[str, Any]:
    # TODO: 敢えて愚直に converter の選択を書いている
    # もう少しかっこよく出来る気もしているが、増えてきてから考える
    # schema の class に変換系の method を持たせるのは可読性が落ちそうなため、やめておく

    if PACKAGE_VERSIONS & {from_, to}:
        raise ValueError(PACKAGE_MESSAGE)

    from_obj = resolve_record_model(from_).model_validate(json_data)

    if from_ == to:
        return json_data

    if from_ == "v1" and to == "v2":
        result = v1_to_v2(cast("DdbjRecordV1", from_obj)).model_dump(exclude_none=True, by_alias=True)
    elif from_ == "v2" and to == "v1":
        result = v2_to_v1(cast("DdbjRecordV2", from_obj)).model_dump(exclude_none=True, by_alias=True)
    else:
        raise ValueError(f"Unsupported conversion from {from_} to {to}")

    resolve_record_model(to).model_validate(result)

    return result


def main() -> None:
    try:
        args = parse_args(sys.argv[1:])

        try:
            with args.input.open("r", encoding="utf-8") as f:
                input_json_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON file {args.input}: {e}") from e

        converted_data = convert_json_data(input_json_data, args.from_, args.to)

        with args.output.open("w", encoding="utf-8") as f:
            json.dump(converted_data, f, indent=2, ensure_ascii=False)

    except (OSError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
