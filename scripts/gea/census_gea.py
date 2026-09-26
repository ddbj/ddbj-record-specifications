# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Tally every item in every GEA metadata file: IDF, SDRF, ADF and CIBEX.

The second of the steps that produce docs/v3-gea-mapping.yml (see scripts/gea/README.md).

Usage:
    uv run scripts/gea/census_gea.py DORDB_DIR CIBEX_DIR OUT.json

DORDB_DIR is what export_dordb.rb wrote: every version of every IDF, SDRF and ADF D-way holds.
CIBEX_DIR holds the CIBEX files, which D-way does not: the cibex/ of the published GEA tree,

    rsync -a a012:/usr/local/resources/gea/cibex/ CIBEX_DIR/

For each item the output records how many files have it, how often it repeats in one file, and
which kinds of value it holds (int / float / bool / empty / str), with a few examples.

`anomalies` counts what the files do that the reading rules have to deal with. Those whose name
starts with `unrepresentable:` are what v3 cannot hold as it stands; build_mapping.py refuses to
write while any is non-zero.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

# The encodings stored files turn out to be in, tried in this order. The files that are not UTF-8
# are CIBEX's, written on Windows (cp1252: plus-minus, degree, curly quotes). Shift_JIS would also
# decode some of them, into the wrong characters. latin-1 decodes anything, and is a last resort.
ENCODINGS = ("utf-8", "cp1252", "latin-1")

EXAMPLES = 5

SDRF_NODES = (
    "Source Name",
    "Sample Name",
    "Extract Name",
    "Labeled Extract Name",
    "Assay Name",
    "Hybridization Name",
    "Scan Name",
    "Normalization Name",
    "Array Data File",
    "Derived Array Data File",
    "Array Data Matrix File",
    "Derived Array Data Matrix File",
    "Image File",
)

MAGE_TAB_ADF_HEADER = {
    "Array Design Name",
    "Version",
    "Provider",
    "Printing Protocol",
    "Technology Type",
    "Technology Type Term Source REF",
    "Technology Type Term Accession Number",
    "Surface Type",
    "Surface Type Term Source REF",
    "Surface Type Term Accession Number",
    "Substrate Type",
    "Substrate Type Term Source REF",
    "Substrate Type Term Accession Number",
    "Sequence Polymer Type",
    "Sequence Polymer Type Term Source REF",
    "Sequence Polymer Type Term Accession Number",
    "Term Source Name",
    "Term Source File",
    "Term Source Version",
}

CIBEX_SECTION = re.compile(r"^([A-Za-z][^\t]*):\s*$")

# The key that names an entry of a CIBEX section: a block without it cannot be told from the
# rest of a table of fields.
CIBEX_ENTRY_KEY = {"Array design": "Array sesign accession", "Hybridization": "Name", "Summary": "Name"}

# The keys each CIBEX section has (MIAME's items, as CIBEX named them).
CIBEX_KEYS = {
    "Array design": {
        "Array sesign accession",  # sic
        "Model name",
        "Technology type",
        "Surface type",
        "Number of features",
        "Reporter type",
        "Strand type",
        "Substrate type",
        "Attachment",
        "Design provider",
        "Array design protocol",
        "Description",
        "File",
    },
    "Hybridization": {
        "Name",
        "Array design accession",
        "Hybridization protocol",
        "Scanning protocol",
        "Description",
        "File",
    },
    "Summary": {"Name", "Normalization protocol", "Transformation protocol", "Description", "File"},
}

# One stored reference (CBX253) separates keys from values with spaces instead of a tab. In this
# section, a line that starts with one of its keys and a space is read as that key and its value.
CIBEX_SPACE_SEPARATED = {
    "Reference": ("Title", "Author", "Journal", "Year", "Volume", "Issue", "Page", "Pubmed ID"),
}


def kind_of(value: str) -> str:
    if value == "":
        return "empty"
    if re.fullmatch(r"[+-]?\d+", value):
        return "int"
    if re.fullmatch(r"[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?", value):
        return "float"
    if value in ("true", "false"):
        return "bool"
    return "str"


def read(path: Path, encodings: Counter[str]) -> str:
    raw = path.read_bytes()
    for encoding in ENCODINGS:
        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        encodings[encoding] += 1
        return text
    raise AssertionError(path)  # latin-1 decodes anything


# Stands in for \\" while the csv module reads a row, so that it is taken as a quote character
# inside the value rather than as the end of a quoted value.
_ESCAPED_QUOTE = "\ue000"


def rows_of(text: str, *, backslash_quotes: bool = False) -> list[list[str]]:
    """Tab-separated rows, quoted as MAGE-TAB quotes ("" inside a quoted value is a quote).

    With backslash_quotes, \\" is a quote too: 39 IDFs and 2 SDRFs write it so. Any other
    backslash is kept as it is (ADF tables have values such as D1Bda10\\2).
    """
    if backslash_quotes:
        if _ESCAPED_QUOTE in text:
            raise ValueError('the text already has the character that stands in for \\"')
        text = text.replace('\\"', _ESCAPED_QUOTE)
    rows = csv.reader(io.StringIO(text, newline=""), delimiter="\t", quotechar='"', doublequote=True)
    return [[cell.replace(_ESCAPED_QUOTE, '"') for cell in row] for row in rows]


class Tally:
    """Per item: files containing it, the most times it occurs in one file, kinds of value."""

    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}

    def file(self, occurrences: dict[str, list[str]], name: str) -> None:
        for item, values in occurrences.items():
            entry = self.items.setdefault(item, {"files": 0, "max_repeat": 0, "kinds": {}, "example": name})
            entry["files"] += 1
            entry["max_repeat"] = max(entry["max_repeat"], len(values))
            for value in values:
                examples = entry["kinds"].setdefault(kind_of(value), [])
                if len(examples) < EXAMPLES and value not in examples and len(value) <= 200:
                    examples.append(value)

    def as_json(self) -> dict[str, Any]:
        return dict(sorted(self.items.items()))


def tag(cell: str) -> str:
    """A MAGE-TAB tag or column heading, without the spaces MAGE-TAB does not count.

    Some SDRFs write `Comment [x]` or `Factor Value [x]` for `Comment[x]` and `Factor Value[x]`.
    """
    return re.sub(r"\s+\[", "[", cell.strip())


def census_idf(path: Path, tally: Tally, encodings: Counter[str]) -> None:
    occurrences: dict[str, list[str]] = defaultdict(list)
    for row in rows_of(read(path, encodings), backslash_quotes=True):
        if not row or not row[0].strip() or row[0].startswith("#"):
            continue
        values = [cell.strip() for cell in row[1:]]
        while values and values[-1] == "":
            values.pop()
        occurrences[tag(row[0])] += values
    tally.file(occurrences, path.name)


def _sdrf_item(column: str, node: str | None) -> str:
    """The column as an item: bracketed names generalised, attributes qualified by their node."""
    general = re.sub(r"\[.*\]$", "[*]", column)
    if column in SDRF_NODES or general == "Factor Value[*]":
        return general
    return f"{general} @ {node}"


def census_sdrf(  # noqa: PLR0913, PLR0917
    path: Path,
    tally: Tally,
    names: dict[str, Counter[str]],
    per_row: Counter[str],
    anomalies: Counter[str],
    encodings: Counter[str],
) -> int | None:
    """Tally one SDRF; return its number of rows.

    A file that is not a tab-separated table starting with Source Name (a CSV, or an IDF saved in
    place of the SDRF) is not read, and None is returned: v3 keeps it as it is stored.
    """
    rows = [row for row in rows_of(read(path, encodings), backslash_quotes=True) if any(cell.strip() for cell in row)]
    if not rows or tag(rows[0][0]) != "Source Name":
        return None

    # A column without a heading (an empty one, or cells past the last) is nothing MAGE-TAB can
    # name. The stored ones hold no values, and are left out.
    width = len(rows[0])
    headed = [index for index, cell in enumerate(rows[0]) if cell.strip()]
    for row in rows[1:]:
        if any(cell.strip() for index, cell in enumerate(row) if index >= width or not rows[0][index].strip()):
            anomalies["unrepresentable: SDRF values in a column without a heading"] += 1
    if len(headed) < width:
        anomalies["SDRFs with an empty column without a heading"] += 1

    header = [tag(rows[0][index]) for index in headed]
    body = [[row[index] for index in headed if index < len(row)] for row in rows[1:]]

    node: str | None = None
    items: list[str] = []
    for index, column in enumerate(header):
        if column in SDRF_NODES:
            node = column
        if column == "Protocol REF":
            following = next((c for c in header[index + 1 :] if c in SDRF_NODES), None)
            items.append(f"Protocol REF > {following}")
        elif column.startswith("Unit["):
            items.append(f"Unit[*] @ {items[-1] if items else None}")
        else:
            items.append(_sdrf_item(column, node))
        if m := re.fullmatch(r"(.+?)\[(.*)\]", column):
            names[m.group(1)][m.group(2)] += 1

    # How many columns of one kind a row has (several Characteristics, several Protocol REFs).
    for item, n in Counter(items).items():
        per_row[item] = max(per_row[item], n)

    occurrences: dict[str, list[str]] = {item: [] for item in items}
    for row in body:
        if len(row) != len(header):
            anomalies["rows whose width differs from the header"] += 1
        for item, value in zip(items, row, strict=False):
            occurrences[item].append(value.strip())

    # The same node name in one column must mean the same node, with the same attributes.
    for index, column in enumerate(header):
        if column not in SDRF_NODES:
            continue
        # A node's attributes run up to the next node or protocol; factor values belong to the row.
        end = next(
            (
                i
                for i in range(index + 1, len(header))
                if header[i] in SDRF_NODES or header[i] == "Protocol REF" or header[i].startswith("Factor Value[")
            ),
            len(header),
        )
        attributes: dict[str, set[tuple[str, ...]]] = defaultdict(set)
        for row in body:
            attributes[row[index]].add(tuple(row[index + 1 : end]))
        if any(len(seen) > 1 for seen in attributes.values()):
            anomalies[f"files where one {column} carries different attributes on different rows"] += 1

    # Columns of the same name hold a list: within one node (several Protocol REFs, a Comment
    # given twice), and the data file columns across the row (data_files[] is one list). v3 keeps
    # a list's values, not its empty cells, so an empty cell with a value after it would move
    # that value. A Unit is not a list of its own: it goes with the column before it.
    segment = 0
    groups: dict[tuple[int, str], list[int]] = defaultdict(list)
    for index, column in enumerate(header):
        if column in SDRF_NODES:
            segment += 1
        if column.startswith("Unit["):
            continue
        groups[(0 if "File" in column and column in SDRF_NODES else segment), column].append(index)
    for indices in groups.values():
        for row in body:
            cells = [row[i].strip() if i < len(row) else "" for i in indices]
            if any(cell == "" and any(cells[j + 1 :]) for j, cell in enumerate(cells)):
                anomalies["unrepresentable: SDRF rows with an empty cell before a value of the same column"] += 1

    tally.file(occurrences, path.name)
    return len(body)


def census_adf(
    path: Path, header_tally: Tally, table_tally: Tally, forms: Counter[str], encodings: Counter[str]
) -> None:
    rows = rows_of(read(path, encodings))
    header: dict[str, list[str]] = defaultdict(list)
    index = 0
    while index < len(rows):
        row = rows[index]
        tag = row[0].strip() if row else ""
        if any(cell.strip() for cell in row) and not (tag.startswith("Comment[") or tag in MAGE_TAB_ADF_HEADER):
            break
        if tag:
            # Positions matter (Term Source Name / File / Version are parallel), so only the
            # trailing empty cells go.
            values = [cell.strip() for cell in row[1:]]
            while values and values[-1] == "":
                values.pop()
            header[tag] += values
        index += 1

    rest = rows[index:]
    first = next((cell.strip() for row in rest for cell in row if cell.strip()), "")
    if first == "[main]":
        forms["MAGE-TAB ADF"] += 1
        rest = rest[1:]
    elif "dummy" in first.lower():
        forms["dummy"] += 1
    else:
        forms["vendor table"] += 1

    header_tally.file(header, path.name)
    if rest:
        table_tally.file({column.strip(): [] for column in rest[0]}, path.name)


def census_cibex(
    path: Path,
    sections: dict[str, Tally],
    shapes: dict[str, Counter[int]],
    anomalies: Counter[str],
    encodings: Counter[str],
) -> None:
    """Sections of `Key<TAB>value` lines; blocks in a section are separated by blank lines, and a
    line with no tab continues the value above it.

    A `* data text field` section holds a `Field<TAB>Description` table describing the columns of
    a data file, and after it, without a heading of their own, more blocks of the section it is
    named after (a `Hybridization data text field` section goes on with hybridizations). Such a
    block is told from the rest of the table (which a blank line may have split) by having only
    keys of that section, among them the one that names an entry (CIBEX_ENTRY_KEY).
    """
    section = "(top)"
    blocks: dict[str, list[dict[str, list[str]]]] = defaultdict(list)
    block: dict[str, list[str]] | None = None
    last_key: str | None = None

    def close() -> None:
        nonlocal block
        if block:
            parent = section.removesuffix(" data text field").removesuffix(" text field")
            keys = CIBEX_KEYS.get(parent, set())
            heading_less = section != parent and "Field" not in block
            if heading_less and set(block) <= keys and CIBEX_ENTRY_KEY[parent] in block:
                blocks[parent].append(block)
            else:
                # A table's rows may be named like an entry's keys (a data column called Name or
                # Description); a block of such rows, cut off by a blank line, could be either.
                if heading_less and set(block) & keys:
                    anomalies["unrepresentable: CIBEX blocks that could be a table's rows or an entry"] += 1
                blocks[section].append(block)
        block = None

    for line in read(path, encodings).replace("\r", "").split("\n"):
        if m := CIBEX_SECTION.match(line):
            close()
            section, last_key = m.group(1), None
            continue
        if not line.strip():
            close()
            last_key = None
            continue
        if block is None:
            block = defaultdict(list)
        spaced = next((key for key in CIBEX_SPACE_SEPARATED.get(section, ()) if line.startswith(key + " ")), None)
        if "\t" in line:
            key, _, value = line.partition("\t")
            block[key.strip()].append(value.strip())
            last_key = key.strip()
        elif spaced is not None:
            anomalies["CIBEX lines separating a key from its value with spaces"] += 1
            block[spaced].append(line[len(spaced) :].strip())
            last_key = spaced
        elif last_key is not None:
            block[last_key][-1] += "\n" + line.strip()
        else:
            block["(line without a key)"].append(line.strip())
    close()

    for name, found in blocks.items():
        shapes[name][len(found)] += 1
        merged: dict[str, list[str]] = defaultdict(list)
        repeats: dict[str, int] = defaultdict(int)
        for each in found:
            for key, values in each.items():
                merged[key] += values
                repeats[key] = max(repeats[key], len(values))
        tally = sections.setdefault(name, Tally())
        tally.file(merged, path.name)
        for key, n in repeats.items():
            tally.items[key]["max_repeat_in_block"] = max(tally.items[key].get("max_repeat_in_block", 0), n)


def census(idfs: list[Path], sdrfs: list[Path], adfs: list[Path], cibexes: list[Path]) -> dict[str, Any]:
    """The tally of the given files, as main writes it."""
    encodings: dict[str, Counter[str]] = defaultdict(Counter)
    idf, sdrf, adf_header, adf_table = Tally(), Tally(), Tally(), Tally()
    sdrf_names: dict[str, Counter[str]] = defaultdict(Counter)
    sdrf_per_row: Counter[str] = Counter()
    anomalies: Counter[str] = Counter()
    adf_forms: Counter[str] = Counter()
    cibex: dict[str, Tally] = {}
    cibex_blocks: dict[str, Counter[int]] = defaultdict(Counter)

    for path in idfs:
        census_idf(path, idf, encodings["idf"])
    read_rows = [census_sdrf(path, sdrf, sdrf_names, sdrf_per_row, anomalies, encodings["sdrf"]) for path in sdrfs]
    for path in adfs:
        census_adf(path, adf_header, adf_table, adf_forms, encodings["adf"])
    for path in cibexes:
        census_cibex(path, cibex, cibex_blocks, anomalies, encodings["cibex"])

    return {
        "files": {kind: sum(counter.values()) for kind, counter in encodings.items()},
        "encodings": {kind: dict(counter) for kind, counter in encodings.items()},
        "anomalies": dict(anomalies),
        "idf": idf.as_json(),
        "sdrf": {
            "items": sdrf.as_json(),
            "rows": sum(n for n in read_rows if n is not None),
            "unread": read_rows.count(None),
            "most_in_a_row": dict(sorted(sdrf_per_row.items())),
            "bracketed_names": {kind: dict(counter.most_common()) for kind, counter in sdrf_names.items()},
        },
        "adf": {"forms": dict(adf_forms), "header": adf_header.as_json(), "table_columns": adf_table.as_json()},
        "cibex": {
            "sections": {name: tally.as_json() for name, tally in sorted(cibex.items())},
            "blocks_per_file": {name: dict(sorted(counter.items())) for name, counter in sorted(cibex_blocks.items())},
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dordb_dir", type=Path)
    parser.add_argument("cibex_dir", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()

    out = census(
        sorted(args.dordb_dir.glob("idf/*/*.idf.txt")),
        sorted(args.dordb_dir.glob("sdrf/*/*.sdrf.txt")),
        sorted(args.dordb_dir.glob("adf/*/*.adf")),
        sorted(args.cibex_dir.glob("*/*.metadata")),
    )

    args.out.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
