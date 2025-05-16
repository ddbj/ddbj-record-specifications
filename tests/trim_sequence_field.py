import json
import sys
from pathlib import Path


def main() -> None:
    args = sys.argv[1:]
    if len(args) != 1:
        print("Usage: python trim_sequence_field.py <input_file>")
        sys.exit(1)

    input_file = Path(args[0]).resolve()
    print(f"Input file: {input_file}")
    if not input_file.exists():
        print(f"Error: File {input_file} does not exist.")
        sys.exit(1)
    output_file = input_file.parent.joinpath(f"{input_file.stem}_trimmed{input_file.suffix}")
    print(f"Output file: {output_file}")

    with input_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if "ENTRIES" in data:
        for entry in data["ENTRIES"]:
            if "sequence" in entry:
                entry["sequence"] = "<trimmed>"

    with output_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    main()
