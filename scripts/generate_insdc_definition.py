"""Generate INSDC feature/qualifier definition YAML from official sources.

This script fetches data from four DDBJ/INSDC official sources and generates
the insdc_feature_table.yaml file:

  1. Google Sheets CSV      - feature x qualifier matrix
  2. DDBJ Qualifier page    - qualifier definitions (value_format, controlled_vocabulary, deprecated)
  3. DDBJ Feature page      - feature descriptions
  4. INSDC ncRNA vocabulary - controlled vocabulary for /ncRNA_class

Usage:
    uv run python scripts/generate_insdc_definition.py            # generate YAML
    uv run python scripts/generate_insdc_definition.py --check    # diff check only
    uv run python scripts/generate_insdc_definition.py --local-csv path --local-qualifier-html path --local-feature-html path --local-ncrna-html path

Note:
    Requires: beautifulsoup4, pyyaml (install via `uv sync --extra scripts`)
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import yaml
from bs4 import BeautifulSoup, Tag

SPREADSHEET_ID = "1qosakEKo-y9JjwUO_OFcmGCUfssxhbFAm5NXUAnT3eM"
CSV_EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv"
QUALIFIER_HTML_URL = "https://www.ddbj.nig.ac.jp/ddbj/qualifiers.html"
FEATURE_HTML_URL = "https://www.ddbj.nig.ac.jp/ddbj/features.html"
NCRNA_VOCABULARY_URL = "https://www.insdc.org/submitting-standards/ncrna-vocabulary/"

OUTPUT_PATH = Path(__file__).resolve().parent.parent.joinpath("ddbj_record", "insdc", "insdc_feature_table.yaml")

# Qualifiers managed by the system, not user-specifiable
SYSTEM_QUALIFIERS = frozenset({"db_xref", "protein_id"})

# Qualifiers where auto-detection of value_format doesn't work.
# These are manually overridden based on INSDC specification.
VALUE_FORMAT_OVERRIDES: dict[str, str] = {
    "estimated_length": "text",  # "unknown or <integer>", treated as text
    "frequency": "text",  # format uses placeholders but is free text
    "mod_base": "text",  # abbreviation from external list
    "ncRNA_class": "controlled_vocabulary",  # <TYPE> from external CV
    "tag_peptide": "text",  # <base_range> is free text
    "translation": "text",  # amino acid sequence, no format dd in HTML
    "transl_table": "controlled_vocabulary",  # range notation in dd
}

# value_format for deprecated qualifiers whose HTML section lacks a <dl> definition
DEPRECATED_VALUE_FORMATS: dict[str, str] = {
    "country": "structured",
}

# Deprecated qualifiers removed from CSV but kept in feature assignments
DEPRECATED_FEATURE_QUALIFIERS: dict[str, dict[str, str]] = {
    "source": {
        "country": "optional",
        "sub_species": "optional",
        "variety": "optional",
    },
}

# Cross-feature constraints (from CSV footnotes and HTML notes)
CROSS_CONSTRAINTS: list[dict[str, Any]] = [
    {
        "type": "mutual_exclusion",
        "qualifiers": ["germline", "rearranged"],
        "message": "/germline and /rearranged are mutually exclusive",
    },
    {
        "type": "mutual_exclusion",
        "qualifiers": ["pseudo", "pseudogene"],
        "message": "/pseudo and /pseudogene are mutually exclusive",
    },
    {
        "type": "dependency",
        "qualifier": "metagenome_source",
        "requires": "environmental_sample",
        "message": "/metagenome_source requires /environmental_sample",
    },
    {
        "type": "dependency",
        "qualifier": "gene_synonym",
        "requires": ["gene", "locus_tag"],
        "message": "/gene_synonym requires /gene or /locus_tag",
    },
    {
        "type": "conditional_mandatory",
        "feature": "CDS",
        "condition": "absent:pseudo,pseudogene",
        "then_mandatory": ["product"],
        "message": "CDS requires /product unless /pseudo or /pseudogene is present",
    },
    {
        "type": "conditional_mandatory",
        "feature": "assembly_gap",
        "condition": "value:gap_type=within scaffold,repeat within scaffold",
        "then_mandatory": ["linkage_evidence"],
        "message": "assembly_gap requires /linkage_evidence when /gap_type is 'within scaffold' or 'repeat within scaffold'",
    },
]

# --- CSV row/column indices ---
SOURCE_HEADER_ROW = 2
SOURCE_DATA_ROW = 3
GENERAL_HEADER_ROW = 7
GENERAL_DATA_START_ROW = 8
FEATURE_NAME_COL = 3
QUALIFIER_START_COL = 4


# --- Data fetching ---


def fetch_url(url: str) -> str:
    with urlopen(url) as response:  # noqa: S310
        return response.read().decode("utf-8")


# --- CSV parser ---


def _parse_section(
    header_row: list[str],
    data_rows: list[list[str]],
) -> dict[str, dict[str, str]]:
    """Parse a CSV section (source or general) into feature -> {qualifier: requirement}.

    header_row contains qualifier names starting at QUALIFIER_START_COL.
    data_rows contain feature data rows with feature name at FEATURE_NAME_COL.
    """
    qualifier_names: list[tuple[int, str]] = []
    for col_idx in range(QUALIFIER_START_COL, len(header_row)):
        name = header_row[col_idx].strip()
        if name:
            qualifier_names.append((col_idx, name))

    features: dict[str, dict[str, str]] = {}

    for row in data_rows:
        if len(row) <= FEATURE_NAME_COL:
            continue
        feature_name = row[FEATURE_NAME_COL].strip()
        if not feature_name:
            continue

        qualifiers: dict[str, str] = {}
        for col_idx, qual_name in qualifier_names:
            if col_idx >= len(row):
                continue
            cell = row[col_idx].strip()
            if not cell:
                continue
            if cell == "◎":
                qualifiers[qual_name] = "mandatory"
            else:
                # ○ or digits (footnotes 1-4) are all optional
                qualifiers[qual_name] = "optional"

        if qualifiers:
            features[feature_name] = qualifiers

    return features


def parse_matrix(csv_text: str) -> dict[str, dict[str, str]]:
    """Parse the feature/qualifier matrix CSV.

    Returns:
        dict mapping feature_name -> {qualifier_name: "mandatory" | "optional"}
        source feature + all general features combined.
    """
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)

    if len(rows) <= GENERAL_DATA_START_ROW:
        print(f"Error: CSV has only {len(rows)} rows, expected more", file=sys.stderr)
        sys.exit(1)

    # Source section
    source_features = _parse_section(
        header_row=rows[SOURCE_HEADER_ROW],
        data_rows=[rows[SOURCE_DATA_ROW]],
    )

    # General section: rows from GENERAL_DATA_START_ROW until feature name is empty
    general_data_rows = [
        row for row in rows[GENERAL_DATA_START_ROW:] if len(row) > FEATURE_NAME_COL and row[FEATURE_NAME_COL].strip()
    ]

    general_features = _parse_section(
        header_row=rows[GENERAL_HEADER_ROW],
        data_rows=general_data_rows,
    )

    # Merge: source first, then general features
    # For source, also include "note" from general section if present (dedup)
    features: dict[str, dict[str, str]] = {}
    features.update(source_features)

    for feat_name, quals in general_features.items():
        if feat_name in features:
            # Merge qualifiers (source already exists, add general quals)
            features[feat_name].update(quals)
        else:
            features[feat_name] = quals

    return features


# --- Qualifier HTML parser ---


def _get_sections_between_h3(soup: BeautifulSoup) -> list[tuple[Tag, list[Tag]]]:
    """Get (h3_tag, [sibling_tags]) pairs for all h3 elements."""
    h3_tags = soup.find_all("h3")
    sections: list[tuple[Tag, list[Tag]]] = []

    for h3 in h3_tags:
        content: list[Tag] = []
        for sib in h3.next_siblings:
            if isinstance(sib, Tag) and sib.name == "h3":
                break
            if isinstance(sib, Tag):
                content.append(sib)
        sections.append((h3, content))

    return sections


def _extract_qualifier_name(h3: Tag) -> str:
    """Extract qualifier name from h3 direct text like '/allele'."""
    for child in h3.children:
        if isinstance(child, str):
            text = child.strip()
            if text:
                name = text.lstrip("/")
                # Normalize curly apostrophe to straight apostrophe (for 3'UTR etc.)
                name = name.replace("\u2019", "'")

                return name

    return ""


def _find_dd_by_dt(dl: Tag, dt_keyword: str, *, partial: bool = False) -> str:
    """Find the <dd> text for a matching <dt> in a <dl>.

    If partial=True, matches when dt_keyword is contained in the dt text.
    Otherwise, matches exact text.
    """
    dts = dl.find_all("dt")
    dds = dl.find_all("dd")
    for dt, dd in zip(dts, dds, strict=False):
        dt_text = dt.get_text(strip=True)
        matched = dt_keyword in dt_text if partial else dt_text == dt_keyword
        if matched:
            return dd.get_text(strip=True)

    return ""


def _find_note_dd_tag(dl: Tag) -> Tag | None:
    """Find the <dd> Tag element for the '備考' <dt> in a <dl>."""
    dts = dl.find_all("dt")
    dds = dl.find_all("dd")
    for dt, dd in zip(dts, dds, strict=False):
        if dt.get_text(strip=True) == "備考":
            return dd  # type: ignore[return-value]

    return None


def _extract_br_items(p_tag: Tag) -> list[str]:
    """Extract items from a <p> tag separated by <br> tags."""

    return [stripped for raw in p_tag.get_text().split("\n") if (stripped := raw.strip())]


def _detect_value_format(format_dd: str, following_p_tags: list[Tag], qualifier_name: str) -> str:
    """Detect value_format from the format <dd> text.

    Returns one of: "none", "controlled_vocabulary", "text", "structured"
    """
    # Check overrides first
    if qualifier_name in VALUE_FORMAT_OVERRIDES:
        return VALUE_FORMAT_OVERRIDES[qualifier_name]

    if not format_dd and not following_p_tags:
        return "structured"

    if "値なし" in format_dd:
        return "none"

    # If format dd starts with a structured pattern like "[CATEGORY:]<text>" or "(pos:<...>)",
    # this is a structured format even if it contains "<text>" or "から選択" for a sub-field.
    starts_with_structure = bool(re.match(r"[\[(]", format_dd))
    if starts_with_structure:
        return "structured"

    # "以下から" or "から選択" patterns indicate controlled_vocabulary,
    if re.search(r"以下から|から選択|タイプから選択", format_dd):
        return "controlled_vocabulary"

    # Inline patterns like "X or Y or Z" (codon_start: "1 or 2 or 3")
    if re.search(r"\b\w+ or \w+ or \w+", format_dd):
        return "controlled_vocabulary"

    # "X, Y, Z の中から選択" (direction: "left, right, both の中から選択")
    if re.search(r"\w+,\s*\w+.*の中から", format_dd):
        return "controlled_vocabulary"

    # Quoted choices with "または" - handle both ASCII and Unicode quotes
    # Unicode: \u201c (LEFT DOUBLE QUOTATION MARK), \u201d (RIGHT DOUBLE QUOTATION MARK)
    if re.search(r'["\u201c][^"\u201d]+["\u201d]\s*または\s*["\u201c][^"\u201d]+["\u201d]', format_dd):
        return "controlled_vocabulary"

    # <text> pattern indicates free text
    if "<text>" in format_dd:
        return "text"

    return "structured"


def _extract_controlled_vocabulary(
    format_dd: str,
    following_p_tags: list[Tag],
    qualifier_name: str,
) -> list[str] | None:
    """Extract controlled vocabulary values from format info.

    Returns list of values, or None if not a controlled_vocabulary type.
    """
    # Special: transl_table has range notation like "(1 - 6, 9 - 16, 21 - 31, 33)"
    # Check before <p> patterns to avoid picking up unrelated notes.
    if qualifier_name == "transl_table":
        return _parse_transl_table_range(format_dd)

    # Pattern B: <p> after </dl> with <br>-separated items
    # This is the most common pattern for controlled_vocabulary
    if following_p_tags:
        for p in following_p_tags:
            items = _extract_br_items(p)
            if len(items) >= 2:
                return items

    # Pattern A: inline "X or Y or Z" (codon_start: "1 or 2 or 3 (全角不可)")
    or_match = re.search(r"([\w.]+(?:\s+or\s+[\w.]+)+)", format_dd)
    if or_match:
        values = [v.strip() for v in or_match.group(1).split(" or ")]

        return values

    # Pattern A: inline "X, Y, Z の中から" (direction: "left, right, both の中から選択")
    comma_match = re.search(r"([\w]+(?:,\s*[\w]+)+)\s*の中から", format_dd)
    if comma_match:
        values = [v.strip() for v in comma_match.group(1).split(",")]

        return values

    # Pattern A: quoted values with "または" (artificial_location)
    # Handle both ASCII quotes and Unicode curly quotes
    quoted = re.findall(r'["\u201c]([^"\u201d]+)["\u201d]', format_dd)
    if len(quoted) >= 2:
        return quoted

    return None


def _parse_transl_table_range(format_dd: str) -> list[str] | None:
    """Parse range notation like '(1 - 6, 9 - 16, 21 - 31, 33)' into individual values."""
    range_match = re.search(r"\(([^)]+)\)", format_dd)
    if not range_match:
        return None

    values: list[str] = []
    for raw in range_match.group(1).split(","):
        segment = raw.strip()
        range_parts = segment.split("-")
        if len(range_parts) == 2:
            start = int(range_parts[0].strip())
            end = int(range_parts[1].strip())
            values.extend(str(n) for n in range(start, end + 1))
        else:
            values.append(segment)

    return values


def _detect_deprecated(
    has_dl: bool,
    content: list[Tag],
) -> dict[str, str] | None:
    """Detect if a qualifier is deprecated.

    Returns dict with 'replacement' and/or 'message', or None.
    """
    if not has_dl:
        # Pattern: no <dl>, only <p> with <span class="red"> (country pattern)
        for elem in content:
            if elem.name == "p" and elem.find("span", class_="red"):
                a_tag = elem.find("a")
                replacement = a_tag.get_text(strip=True).lstrip("/") if a_tag else ""
                result: dict[str, str] = {"message": elem.get_text(strip=True)}
                if replacement:
                    result["replacement"] = replacement

                return result

        return None

    # Check 備考 for deprecation keywords
    for elem in content:
        if elem.name != "dl":
            continue
        note_text = _find_dd_by_dt(elem, "備考")
        if not note_text:
            continue

        # "記載しないでください" with link to replacement (pseudo -> pseudogene)
        if "記載しないでください" in note_text:
            result = {"message": note_text}
            note_dd = _find_note_dd_tag(elem)
            if note_dd:
                a_tag = note_dd.find("a")
                if a_tag:
                    result["replacement"] = a_tag.get_text(strip=True).lstrip("/")

            return result

        # "廃止予定" or "廃止" pattern (sub_species, variety)
        if "廃止" in note_text:
            return {"message": note_text}

    return None


def parse_qualifiers(html: str) -> dict[str, dict[str, Any]]:
    """Parse qualifier definitions from DDBJ qualifier HTML page.

    Returns:
        dict mapping qualifier_name -> {
            value_format: str,
            description: str,
            controlled_vocabulary: list[str] | None,
            deprecated: dict | None,
        }
    """
    soup = BeautifulSoup(html, "html.parser")
    sections = _get_sections_between_h3(soup)
    qualifiers: dict[str, dict[str, Any]] = {}

    for h3, content in sections:
        qual_name = _extract_qualifier_name(h3)
        if not qual_name or qual_name in SYSTEM_QUALIFIERS:
            continue

        # Check for <dl> elements
        dls = [e for e in content if e.name == "dl"]
        has_dl = len(dls) > 0

        # Detect deprecated first
        deprecated = _detect_deprecated(has_dl, content)

        if not has_dl:
            # Deprecated qualifier with no definition (e.g. /country)
            # value_format will be resolved during merge with existing YAML
            info: dict[str, Any] = {"value_format": "", "description": ""}
            if deprecated:
                info["deprecated"] = deprecated
            qualifiers[qual_name] = info
            continue

        # Get format dd text from first <dl>
        format_dd = _find_dd_by_dt(dls[0], "書式", partial=True)

        # Get <p> tags that follow the first <dl> (before the next <dl> or end)
        following_p_tags: list[Tag] = []
        first_dl_found = False
        for elem in content:
            if elem.name == "dl":
                if first_dl_found:
                    break
                first_dl_found = True
                continue
            if first_dl_found and elem.name == "p":
                following_p_tags.append(elem)

        # Detect value_format
        value_format = _detect_value_format(format_dd, following_p_tags, qual_name)

        # Extract controlled vocabulary
        cv: list[str] | None = None
        if value_format == "controlled_vocabulary":
            cv = _extract_controlled_vocabulary(format_dd, following_p_tags, qual_name)

        # Get description (from 定義 dd)
        description = _find_dd_by_dt(dls[0], "定義")

        info = {"value_format": value_format, "description": description}
        if cv:
            info["controlled_vocabulary"] = cv
        if deprecated:
            info["deprecated"] = deprecated

        qualifiers[qual_name] = info

    return qualifiers


# --- Feature HTML parser ---


def parse_features(html: str) -> dict[str, str]:
    """Parse feature descriptions from DDBJ feature HTML page.

    Returns:
        dict mapping feature_name -> description
    """
    soup = BeautifulSoup(html, "html.parser")
    sections = _get_sections_between_h3(soup)
    features: dict[str, str] = {}

    for h3, content in sections:
        feat_name = _extract_qualifier_name(h3)
        if not feat_name:
            continue

        # First <p> after h3 is the description
        for elem in content:
            if elem.name == "p":
                features[feat_name] = elem.get_text(strip=True)
                break

    return features


# --- ncRNA vocabulary parser ---


def parse_ncrna_vocabulary(html: str) -> list[str]:
    """Parse ncRNA class vocabulary from INSDC vocabulary page.

    Each vocabulary entry is a <p> starting with <strong>term_name</strong>.
    """
    soup = BeautifulSoup(html, "html.parser")
    content = soup.find("div", class_="page-content")
    if not content:
        return []

    items: list[str] = []
    for p in content.find_all("p"):  # type: ignore[union-attr]
        strong = p.find("strong")
        if not strong:
            continue
        bold_text = strong.get_text(strip=True).rstrip(".")
        match = re.match(r"^([A-Za-z]\w*)", bold_text)
        if not match:
            continue
        term = match.group(1)
        if term not in items:
            items.append(term)

    return items


# --- Merge with existing YAML ---


def _build_qualifier_entry(
    qualifier_name: str,
    html_info: dict[str, Any] | None,
    existing_info: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a single qualifier entry from HTML-derived data.

    HTML is the primary source. Existing YAML is used only for hand-managed
    fields (regex) that cannot be derived from official sources.
    """
    entry: dict[str, Any] = {}

    # value_format: prefer HTML, fall back to DEPRECATED_VALUE_FORMATS
    if html_info and html_info.get("value_format"):
        entry["value_format"] = html_info["value_format"]
    elif qualifier_name in DEPRECATED_VALUE_FORMATS:
        entry["value_format"] = DEPRECATED_VALUE_FORMATS[qualifier_name]
    else:
        entry["value_format"] = "text"

    # description: from HTML
    if html_info and html_info.get("description"):
        entry["description"] = html_info["description"]
    else:
        entry["description"] = ""

    # controlled_vocabulary: from HTML
    if html_info and html_info.get("controlled_vocabulary"):
        entry["controlled_vocabulary"] = html_info["controlled_vocabulary"]

    # deprecated: from HTML
    if html_info and html_info.get("deprecated"):
        entry["deprecated"] = html_info["deprecated"]

    # regex: preserve from existing (hand-managed, not derivable from sources)
    if existing_info and existing_info.get("regex"):
        entry["regex"] = existing_info["regex"]

    return entry


def build_definition(
    matrix: dict[str, dict[str, str]],
    html_qualifiers: dict[str, dict[str, Any]],
    html_features: dict[str, str],
    existing_yaml_path: Path,
) -> dict[str, Any]:
    """Build complete YAML definition from official sources.

    HTML/CSV are the primary sources. Existing YAML is used only for
    hand-managed fields (regex) that cannot be derived from official sources.
    """
    existing: dict[str, Any] = {}
    if existing_yaml_path.exists():
        with existing_yaml_path.open("r", encoding="utf-8") as f:
            existing = yaml.safe_load(f) or {}

    existing_qualifiers: dict[str, Any] = existing.get("qualifiers", {})

    # Collect all qualifier names from CSV matrix and HTML
    all_qual_names: set[str] = set()
    for quals in matrix.values():
        all_qual_names.update(quals.keys())
    all_qual_names.update(html_qualifiers.keys())

    # Build qualifiers section
    qualifiers: dict[str, Any] = {}
    for qual_name in sorted(all_qual_names):
        html_info = html_qualifiers.get(qual_name)
        existing_info = existing_qualifiers.get(qual_name)
        qualifiers[qual_name] = _build_qualifier_entry(qual_name, html_info, existing_info)

    # Build features section
    features: dict[str, Any] = {}
    for feat_name in sorted(matrix.keys()):
        feat_entry: dict[str, Any] = {}

        # Description: from HTML
        if html_features.get(feat_name):
            feat_entry["description"] = html_features[feat_name]
        else:
            feat_entry["description"] = ""

        # Qualifiers: from CSV matrix + deprecated qualifiers
        feat_quals = dict(matrix[feat_name])
        if feat_name in DEPRECATED_FEATURE_QUALIFIERS:
            for q_name, q_req in DEPRECATED_FEATURE_QUALIFIERS[feat_name].items():
                if q_name not in feat_quals:
                    feat_quals[q_name] = q_req

        feat_entry["qualifiers"] = dict(sorted(feat_quals.items()))
        features[feat_name] = feat_entry

    # Build full YAML structure
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result: dict[str, Any] = {
        "meta": {
            "insdc_version": existing.get("meta", {}).get("insdc_version", "11.3"),
            "generated_at": now,
            "sources": [
                f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/",
                QUALIFIER_HTML_URL,
                FEATURE_HTML_URL,
                NCRNA_VOCABULARY_URL,
            ],
        },
        "qualifiers": qualifiers,
        "features": features,
        "cross_constraints": CROSS_CONSTRAINTS,
    }

    return result


# --- Diff report ---


def diff_report(generated: dict[str, Any], existing: dict[str, Any]) -> list[str]:
    """Generate a human-readable diff report between generated and existing YAML."""
    lines: list[str] = []

    # --- Feature matrix diff ---
    lines.append("=== Feature Matrix Diff ===")
    gen_feats = set(generated.get("features", {}).keys())
    ext_feats = set(existing.get("features", {}).keys())

    feat_ok = 0
    feat_warn = 0

    for name in sorted(gen_feats | ext_feats):
        if name in gen_feats and name not in ext_feats:
            lines.append(f"  [NEW] Feature '{name}' in generated but not in existing YAML")
            feat_warn += 1
        elif name not in gen_feats and name in ext_feats:
            lines.append(f"  [REMOVED] Feature '{name}' in existing YAML but not in generated")
            feat_warn += 1
        else:
            gen_quals = generated["features"][name].get("qualifiers", {})
            ext_quals = existing["features"][name].get("qualifiers", {})
            if gen_quals != ext_quals:
                lines.append(f"  [DIFF] Feature '{name}' qualifiers differ:")
                gen_set = set(gen_quals.keys())
                ext_set = set(ext_quals.keys())
                lines.extend(f"    + {q}: {gen_quals[q]}" for q in sorted(gen_set - ext_set))
                lines.extend(f"    - {q}: {ext_quals[q]}" for q in sorted(ext_set - gen_set))
                lines.extend(
                    f"    ~ {q}: {ext_quals[q]} -> {gen_quals[q]}"
                    for q in sorted(gen_set & ext_set)
                    if gen_quals[q] != ext_quals[q]
                )
                feat_warn += 1
            else:
                feat_ok += 1

    lines.append(f"  Features: {feat_ok} OK, {feat_warn} warnings")
    lines.append("")

    # --- Qualifier diff ---
    lines.append("=== Qualifier Diff ===")
    gen_quals = generated.get("qualifiers", {})
    ext_quals = existing.get("qualifiers", {})

    qual_ok = 0
    qual_warn = 0

    for name in sorted(set(gen_quals.keys()) | set(ext_quals.keys())):
        if name in gen_quals and name not in ext_quals:
            lines.append(f"  [NEW] Qualifier '{name}' in generated but not in existing YAML")
            qual_warn += 1
            continue
        if name not in gen_quals and name in ext_quals:
            lines.append(f"  [REMOVED] Qualifier '{name}' in existing YAML but not in generated")
            qual_warn += 1
            continue

        gen_q = gen_quals[name]
        ext_q = ext_quals[name]
        diffs: list[str] = []

        diffs.extend(
            f"    {key}: {ext_q.get(key)!r} -> {gen_q.get(key)!r}"
            for key in ["value_format"]
            if gen_q.get(key) != ext_q.get(key)
        )

        gen_cv = gen_q.get("controlled_vocabulary", [])
        ext_cv = ext_q.get("controlled_vocabulary", [])
        if gen_cv != ext_cv and (gen_cv or ext_cv):
            diffs.append("    controlled_vocabulary differs:")
            diffs.append(f"      existing: {ext_cv}")
            diffs.append(f"      generated: {gen_cv}")

        gen_dep = gen_q.get("deprecated")
        ext_dep = ext_q.get("deprecated")
        if gen_dep != ext_dep and (gen_dep or ext_dep):
            diffs.append(f"    deprecated: {ext_dep!r} -> {gen_dep!r}")

        if diffs:
            lines.append(f"  [DIFF] Qualifier '{name}':")
            lines.extend(diffs)
            qual_warn += 1
        else:
            qual_ok += 1

    lines.append(f"  Qualifiers: {qual_ok} OK, {qual_warn} warnings")
    lines.append("")

    # --- Summary ---
    lines.append("=== Summary ===")
    lines.append(f"Features: {feat_ok} OK, {feat_warn} warnings")
    lines.append(f"Qualifiers: {qual_ok} OK, {qual_warn} warnings")

    return lines


# --- YAML output ---


def _yaml_representer_str(dumper: yaml.Dumper, data: str) -> Any:
    """Use quoted style for strings that need it (e.g. 3'UTR, 5'UTR)."""
    if data and (data[0].isdigit() or "'" in data):
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')

    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


def write_yaml(data: dict[str, Any], path: Path) -> None:
    """Write YAML with consistent formatting."""
    dumper = yaml.Dumper
    dumper.add_representer(str, _yaml_representer_str)

    with path.open("w", encoding="utf-8") as f:
        yaml.dump(
            data,
            f,
            Dumper=dumper,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=120,
        )


# --- CLI ---


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate INSDC feature/qualifier definition YAML from official sources.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only show diff report without overwriting the YAML file.",
    )
    parser.add_argument(
        "--local-csv",
        type=Path,
        help="Use local CSV file instead of fetching from Google Sheets.",
    )
    parser.add_argument(
        "--local-qualifier-html",
        type=Path,
        help="Use local HTML file instead of fetching qualifier page.",
    )
    parser.add_argument(
        "--local-feature-html",
        type=Path,
        help="Use local HTML file instead of fetching feature page.",
    )
    parser.add_argument(
        "--local-ncrna-html",
        type=Path,
        help="Use local HTML file instead of fetching INSDC ncRNA vocabulary page.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Fetch data
    if args.local_csv:
        print(f"Reading CSV from {args.local_csv} ...")
        csv_text = args.local_csv.read_text(encoding="utf-8")
    else:
        print(f"Fetching CSV from {CSV_EXPORT_URL} ...")
        csv_text = fetch_url(CSV_EXPORT_URL)

    if args.local_qualifier_html:
        print(f"Reading qualifier HTML from {args.local_qualifier_html} ...")
        qualifier_html = args.local_qualifier_html.read_text(encoding="utf-8")
    else:
        print(f"Fetching qualifier HTML from {QUALIFIER_HTML_URL} ...")
        qualifier_html = fetch_url(QUALIFIER_HTML_URL)

    if args.local_feature_html:
        print(f"Reading feature HTML from {args.local_feature_html} ...")
        feature_html = args.local_feature_html.read_text(encoding="utf-8")
    else:
        print(f"Fetching feature HTML from {FEATURE_HTML_URL} ...")
        feature_html = fetch_url(FEATURE_HTML_URL)

    if args.local_ncrna_html:
        print(f"Reading ncRNA vocabulary HTML from {args.local_ncrna_html} ...")
        ncrna_html = args.local_ncrna_html.read_text(encoding="utf-8")
    else:
        print(f"Fetching ncRNA vocabulary HTML from {NCRNA_VOCABULARY_URL} ...")
        ncrna_html = fetch_url(NCRNA_VOCABULARY_URL)

    # Parse
    print("Parsing CSV matrix ...")
    matrix = parse_matrix(csv_text)
    print(f"  Found {len(matrix)} features")

    print("Parsing qualifier HTML ...")
    html_qualifiers = parse_qualifiers(qualifier_html)
    print(f"  Found {len(html_qualifiers)} qualifiers")

    print("Parsing feature HTML ...")
    html_features = parse_features(feature_html)
    print(f"  Found {len(html_features)} features")

    print("Parsing ncRNA vocabulary ...")
    ncrna_cv = parse_ncrna_vocabulary(ncrna_html)
    print(f"  Found {len(ncrna_cv)} ncRNA classes")

    # Inject ncRNA_class CV into qualifier info
    if ncrna_cv and "ncRNA_class" in html_qualifiers:
        html_qualifiers["ncRNA_class"]["controlled_vocabulary"] = ncrna_cv

    # Build definition
    print("Building YAML definition ...")
    generated = build_definition(matrix, html_qualifiers, html_features, OUTPUT_PATH)

    # Load existing for diff
    existing: dict[str, Any] = {}
    if OUTPUT_PATH.exists():
        with OUTPUT_PATH.open("r", encoding="utf-8") as f:
            existing = yaml.safe_load(f) or {}

    # Diff report
    print()
    report = diff_report(generated, existing)
    for line in report:
        print(line)

    if args.check:
        print("\n--check mode: YAML not overwritten.")
        # Exit with error if there are warnings
        warning_count = sum(1 for line in report if "[DIFF]" in line or "[NEW]" in line or "[REMOVED]" in line)
        if warning_count > 0:
            sys.exit(1)
    else:
        write_yaml(generated, OUTPUT_PATH)
        print(f"\nYAML written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
