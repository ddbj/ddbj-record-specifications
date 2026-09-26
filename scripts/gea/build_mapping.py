# /// script
# requires-python = ">=3.10"
# dependencies = ["pydantic", "pyyaml"]
# ///
"""Write docs/v3-gea-mapping.yml: where in v3 each item of GEA's metadata goes.

The last of the steps (see scripts/gea/README.md).

Usage:
    uv run scripts/gea/build_mapping.py CENSUS.json docs/v3-gea-mapping.yml

CENSUS.json comes from census_gea.py. Every item in it must have a rule here, and the rules must
agree with what the stored files hold: an item that repeats (within a file, a row or a block)
goes into a list, and a value typed int / float / bool in v3 never held anything else. The
script lists what fails and writes nothing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from v3_locations import CONTAINER, resolve, segments, unreadable

SDRF = "investigation.sdrf[]"
CIBEX = "investigation.legacy.cibex"

# --- IDF: one tag per line, its values across the line. Tags of one group (Person, Protocol,
# Experimental Factor) are parallel lists: the n-th values of each describe the n-th item.

IDF = {
    "MAGE-TAB Version": "investigation.magetab_version",
    "Investigation Title": "investigation.title",
    "Experiment Description": "investigation.description",
    "Experimental Design": "investigation.experimental_designs[]",
    "Experimental Factor Name": "investigation.experimental_factors[].name",
    "Experimental Factor Type": "investigation.experimental_factors[].type",
    "Person First Name": "submission.submitters[].first_name",
    "Person Last Name": "submission.submitters[].last_name",
    "Person Affiliation": "submission.submitters[].organizations[].name (その人の 1 つ目の organization)",
    "Person Roles": "submission.submitters[].role",
    "Protocol Name": "investigation.protocols[].name",
    "Protocol Type": "investigation.protocols[].type",
    "Protocol Description": "investigation.protocols[].description",
    "PubMed ID": "investigation.publications[].pubmed_id",
    "Publication DOI": "investigation.publications[].doi",
    "Public Release Date": "submission.hold_date",
    "Comment[Public Release Date]": "submission.hold_date (古い版の書き方)",
    "SDRF File": "investigation.sdrf_file",
    "Comment[GEAAccession]": "investigation.accession",
    "Comment[SecondaryAccession]": "investigation.identifiers[secondary].value",
    "Comment[BioProject]": "relations[part_of bioproject].target.id",
    "Comment[Related study]": 'relations[related_to].target.id (値の "DB:" は target.db に)',
    "Comment[AEExperimentType]": "investigation.experiment_type",
    "Comment[Number of channel]": "investigation.channel_type",
    "Comment[Array Design REF]": "investigation.array_design_ref",
    "Comment[Last Update Date]": "investigation.legacy.last_update_date",
    "Comment[CIBEX Accept Date]": "investigation.legacy.cibex_accept_date",
    "Comment[CIBEX Public Release Date]": "investigation.legacy.cibex_public_release_date",
    "Comment[CIBEX Submitter]": "investigation.legacy.cibex_submitter",
    "Comment[DBCLS]": "investigation.dbcls_approval",
    "Comment[NBDC]": "investigation.nbdc_approval",
}

# --- SDRF: items as census_gea.py names them. A row goes into one SdrfRow.

NODES = {
    "Source Name": "source",
    "Extract Name": "extract",
    "Labeled Extract Name": "labeled_extract",
    "Assay Name": "assay",
    "Array Data File": "data_files[]",
    "Derived Array Data File": "data_files[]",
    "Array Data Matrix File": "data_files[]",
    "Derived Array Data Matrix File": "data_files[]",
}

NODE_ATTRIBUTES = {
    "Material Type": "material_type",
    "Label": "label",
    "Technology Type": "technology_type",
    "Array Design REF": "array_design_ref",
}

BRACKETED = " (角括弧の中が name)"

# An SDRF census_gea.py does not read as a table.
SDRF_UNREAD = "(unread)"

# --- ADF header: one tag per line. The table after it goes into the file as it is.

ADF = {
    "Comment[GEAAccession]": "array_design.accession",
    "Array Design Name": "array_design.name",
    "Version": "array_design.version",
    "Provider": "array_design.provider",
    "Printing Protocol": "array_design.printing_protocol",
    "Technology Type": "array_design.technology_type",
    "Surface Type": "array_design.surface_type",
    "Substrate Type": "array_design.substrate_type",
    "Sequence Polymer Type": "array_design.sequence_polymer_type",
    "Term Source Name": "array_design.term_sources[].name",
    "Term Source File": "array_design.term_sources[].file",
    "Term Source Version": "array_design.term_sources[].version",
    "Comment[Organism]": "array_design.organism.name",
    "Comment[Description]": "array_design.description",
    "Comment[Public Release Date]": "submission.hold_date",
    "Comment[SubmittedName]": "array_design.submitted_name",
    "Comment[CIBEX Public Release Date]": "array_design.legacy.cibex_public_release_date",
}
ADF_TABLE = "(table)"

# --- CIBEX: `Section / Key`. Blocks of a section are the entries of its list.

CIBEX_SECTIONS = {
    "(top)": CIBEX,
    "Experiment": f"{CIBEX}.experiment",
    "Submitter": f"{CIBEX}.submitters[]",
    "Reference": f"{CIBEX}.references[]",
    "Protocol": f"{CIBEX}.protocols[]",
    "Array design": f"{CIBEX}.array_designs[]",
    "Sample": f"{CIBEX}.samples[]",
    "Labeled Extract": f"{CIBEX}.labeled_extracts[]",
    "Hybridization": f"{CIBEX}.hybridizations[]",
    "Summary": f"{CIBEX}.summaries[]",
}

# The field a key goes into, where it is not the key in snake_case.
CIBEX_FIELDS = {
    "(top)": {"CIBEX accession": "accession"},
    "Experiment": {
        "Experiment title": "title",
        "Experimental design type": "design_type",
        "Experimental factor": "factor",
        "Number of hybridization": "number_of_hybridizations",
        "Experimental description": "description",
    },
    "Array design": {"Array sesign accession": "accession"},  # sic
}

# A `* data text field` section is a table of the columns of the data files of the entry it
# follows: each key is a column's name, each value its description.
CIBEX_DATA_FIELDS = {
    "Array design text field": f"{CIBEX}.array_designs[].data_fields[]",
    "Hybridization data text field": f"{CIBEX}.hybridizations[].data_fields[]",
    "Summary data text field": f"{CIBEX}.summaries[].data_fields[]",
}


def snake(key: str) -> str:
    return re.sub(r"\W+", "_", key.strip().lower()).strip("_")


def idf_rule(tag: str) -> str | None:
    if re.fullmatch(r"Comment\[AdditionalFile:.+\]", tag):
        return "investigation.additional_files[].name (角括弧の中の : の後が type)"
    return IDF.get(tag)


DATA_FILES = {node for node, field in NODES.items() if field == "data_files[]"}


def sdrf_rule(item: str) -> str | None:
    if item == SDRF_UNREAD:
        return "investigation.legacy.unread_sdrf (SDRF をファイルのまま)"
    if item in NODES:
        return f"{SDRF}.{NODES[item]}.name" + (" (type は列の名前)" if NODES[item] == "data_files[]" else "")
    if m := re.fullmatch(r"Protocol REF > (.+)", item):
        following = NODES.get(m.group(1))
        return following and f"{SDRF}.{following}.protocol_refs[] (直後のノードの protocol)"
    if item == "Factor Value[*]":
        return f"{SDRF}.factor_values[].value" + BRACKETED
    if item == "Unit[*] @ Factor Value[*]":
        return f"{SDRF}.factor_values[].unit (直前の Factor Value の unit。角括弧の中が unit_type)"
    if not (m := re.fullmatch(r"(.+) @ (.+)", item)):
        return None
    column, owner = m.group(1), NODES.get(m.group(2))
    if owner is None:
        return None
    # A data file carries only comments (the Factor Values and Units after it are the row's, above).
    # Anything else written after one is MAGE-TAB's nowhere.
    if m.group(2) in DATA_FILES and column != "Comment[*]":
        return f"{SDRF}.misplaced_columns[].value (name は列の見出し)"
    node = owner
    if column == "Characteristics[*]" and node == "source":
        return f"{SDRF}.source.characteristics[].value" + BRACKETED
    if column == "Comment[*]":
        return f"{SDRF}.{node}.comments[].value" + BRACKETED
    field = NODE_ATTRIBUTES.get(column)
    return field and f"{SDRF}.{node}.{field}"


def adf_rule(tag: str) -> str | None:
    if tag == ADF_TABLE:
        return "array_design.file (ADF をファイルのまま)"
    return ADF.get(tag)


def cibex_rule(path: str) -> str | None:
    section, _, key = path.partition(" / ")
    if section in CIBEX_DATA_FIELDS:
        base = CIBEX_DATA_FIELDS[section]
        return CONTAINER if key == "Field" else f"{base}.field (キーが field、値が description)"
    if section not in CIBEX_SECTIONS:
        return None
    field = CIBEX_FIELDS.get(section, {}).get(key, snake(key))
    return f"{CIBEX_SECTIONS[section]}.{field}"


RULES = {"idf": idf_rule, "sdrf": sdrf_rule, "adf": adf_rule, "cibex": cibex_rule}


def items(census: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    """Every item of the census, per part, with what the census says of it."""
    cibex = {
        f"{section} / {key}": entry
        for section, keys in census["cibex"]["sections"].items()
        for key, entry in keys.items()
        if section not in CIBEX_DATA_FIELDS or key == "Field"
    }
    # The keys of a data text field are the columns' names, which are the file's own: one row
    # stands for them all.
    for section in CIBEX_DATA_FIELDS:
        if section in census["cibex"]["sections"]:
            cibex[f"{section} / (列の名前)"] = {
                "files": max(k["files"] for k in census["cibex"]["sections"][section].values())
            }

    return {
        "idf": census["idf"],
        "sdrf": {
            **{
                item: {**entry, "most_in_a_row": census["sdrf"]["most_in_a_row"].get(item, 1)}
                for item, entry in census["sdrf"]["items"].items()
            },
            **({SDRF_UNREAD: {"files": len(census["sdrf"]["unread"])}} if census["sdrf"]["unread"] else {}),
        },
        "adf": {**census["adf"]["header"], ADF_TABLE: {"files": sum(census["adf"]["forms"].values())}},
        "cibex": cibex,
    }


def disagreements(part: str, location: str, entry: dict[str, Any]) -> list[str]:
    if location == CONTAINER:
        return []

    try:
        cannot = unreadable(resolve(location), set(entry.get("kinds", {})))
    except LookupError as e:
        return [str(e)]

    problems = []
    if cannot:
        problems.append(f"stored values include {sorted(cannot)}, which the type cannot hold")

    # Repeats within one file (IDF), row (SDRF) or block (CIBEX) need a list of their own:
    # below the row for the SDRF, anywhere for the rest.
    repeats = {
        "idf": entry.get("max_repeat", 1) > 1,
        "sdrf": entry.get("most_in_a_row", 1) > 1,
        "adf": entry.get("max_repeat", 1) > 1,
        "cibex": entry.get("max_repeat_in_block", 1) > 1,
    }[part]
    own = segments(location)
    below = own[own.index("sdrf[]") + 1 :] if "sdrf[]" in own else own
    if repeats and not any(segment.endswith("[]") for segment in below):
        problems.append("repeats, but goes into no list of its own")

    return problems


HEADER = """\
# GEA のメタデータ（MAGE-TAB の IDF / SDRF、アレイ設計の ADF、CIBEX）の項目を、v3 のどこに置くか。
# 考え方は docs/v3-gea.md、作り方は scripts/gea/README.md。このファイルは
# scripts/gea/build_mapping.py が書くので、手で直さない。
#
# 対象は D-way の dordb にある IDF / SDRF / ADF の全ての版と、a012:/usr/local/resources/gea/cibex の
# CIBEX のファイルに現れる項目。
#
#   idf     IDF の行の見出し
#   sdrf    SDRF の列。角括弧の中は [*] にまとめ、属性の列は直前のノードを @ の後に書く。
#           Protocol REF は、直後のノードを > の後に書く。(unread) は表として読まない SDRF
#   adf     ADF の見出しの行。(table) は見出しの後の表
#   cibex   CIBEX の「節 / キー」
#
# 値の読み方は docs/v3-sra-mapping.yml と同じ:
#   (container)          値を持たない入れ物
#   a.b[]                b は list。[] の中の語は注記で、要素の type と、relation なら target.db
#   ... (注記)           読み手のための補足
#
# 数はその項目を含むファイルの数。IDF / SDRF / ADF は版を 1 つのファイルと数える。
"""


def quote(value: str) -> str:
    return yaml.safe_dump(value, allow_unicode=True, width=1000).strip().removesuffix("...").strip()


def width(text: str) -> int:
    """Columns text takes in a fixed-width font: wide (Japanese) characters take two."""
    return sum(2 if unicodedata.east_asian_width(char) in "WF" else 1 for char in text)


def render(parts: dict[str, dict[str, dict[str, Any]]]) -> str:
    lines = [HEADER]
    for part, found in parts.items():
        keys = {item: quote(item) + ":" for item in found}
        column = max(width(key) for key in keys.values())
        lines.append(f"{part}:")
        for item in sorted(found):
            location = RULES[part](item)
            files = found[item].get("files")
            note = f"  # {files:,} ファイル" if files is not None else ""
            padding = " " * (column - width(keys[item]))
            lines.append(f"  {keys[item]}{padding} {quote(location or '')}{note}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("census", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()

    census = json.loads(args.census.read_text(encoding="utf-8"))
    parts = items(census)

    problems = [f"{name}: {n}" for name, n in census["anomalies"].items() if name.startswith("unrepresentable:") and n]
    for part, found in parts.items():
        for item, entry in sorted(found.items()):
            location = RULES[part](item)
            if location is None:
                problems.append(f"{part}: {item}: no rule")
            else:
                problems += [f"{part}: {item}: {problem}" for problem in disagreements(part, location, entry)]

    if problems:
        print(*problems, sep="\n", file=sys.stderr)
        sys.exit(1)

    args.out.write_text(render(parts), encoding="utf-8")


if __name__ == "__main__":
    main()
