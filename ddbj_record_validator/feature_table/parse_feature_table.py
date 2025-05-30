import html
import json
import re
from collections import OrderedDict
from typing import Dict, List, Optional

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from ddbj_record_validator.utils import get_feature_table_dir_path

INSDC_FEATURE_TABLE_URL = "https://www.insdc.org/submitting-standards/feature-table/"
INSDC_FEATURE_TABLE_HTML_NAME = "meta/source.html"


def fetch_feature_table_html(force_fetch: bool = False) -> str:
    feature_table_dir_path = get_feature_table_dir_path()
    html_path = feature_table_dir_path.joinpath(INSDC_FEATURE_TABLE_HTML_NAME).resolve()
    html_path.parent.mkdir(parents=True, exist_ok=True)

    if html_path.exists() and not force_fetch:
        with html_path.open("r", encoding="utf-8") as file:
            return file.read()

    with httpx.Client(timeout=10) as client:
        response = client.get(INSDC_FEATURE_TABLE_URL)
        response.raise_for_status()

        content = response.content.decode("utf-8")
        with html_path.open("w", encoding="utf-8") as file:
            file.write(content)

    return content


class Feature(BaseModel):
    feature_key: str = Field(
        ...,
        description="The feature key name",
    )
    definition: str = Field(
        ...,
        description="The definition of the key",
    )
    # mandatory_qualifiers: Qualifiers = Field(
    mandatory_qualifiers: List[str] = Field(
        default_factory=list,
        description="Qualifiers required with the key; if there are no mandatory qualifiers, this field is omitted.",
    )
    # optional_qualifiers: Qualifiers = Field(
    optional_qualifiers: List[str] = Field(
        default_factory=list,
        description="Optional qualifiers associated with the key",
    )
    organism_scope: Optional[str] = Field(
        None,
        description="Valid organisms for the key; if the scope is any organism, this field is omitted.",
        examples=["eukaryotes", "eukaryotes and eukaryotic viruses"]
    )
    molecule_scope: Optional[str] = Field(
        None,
        description="Valid molecule types; if the scope is any molecule type, this field is omitted.",
        examples=["DNA", "any"]
    )
    references: Optional[str] = Field(
        None,
        description=(
            "Citations of published reports, usually supporting the feature consensus sequence. "
            "Note: In the current data, this field is consistently absent (None)."
        ),
    )
    comment: Optional[str] = Field(
        None,
        description="Comments and clarifications",
    )
    example: Optional[str] = Field(
        None,
        description="Example of the feature key in a sequence",
        examples=["/ncRNA_class=\"miRNA\"", "/ncRNA_class=\"siRNA\"", "/ncRNA_class=\"scRNA\""]
    )


def _parse_section_lines(header: str, lines: List[str]) -> str | List[str]:
    lines[0] = lines[0][len(header):].strip()
    cleaned = [line.strip() for line in lines if line.strip()]

    as_string = {"feature key", "definition", "comment", "organism scope", "molecule scope", "references", "example"}
    if header.lower() in as_string:
        return " ".join(cleaned)
    return cleaned


def extract_features_from_html(html: str) -> List[Feature]:
    SEC_HEADER = "7.2 Appendix II: Feature keys reference"
    COL_HEADERS = [
        "feature key",
        "definition",
        "mandatory qualifiers",
        "optional qualifiers",
        "organism scope",
        "molecule scope",
        "references",
        "comment",
        "example",
    ]

    soup = BeautifulSoup(html, "lxml")

    h3 = soup.find("h3", string=lambda t: t and SEC_HEADER in t)
    if not h3:
        raise ValueError(f"Header '{SEC_HEADER}' not found in the HTML file.")

    pre = h3.find_next_sibling("pre")
    if not pre:
        raise ValueError(f"<pre> tag not found after header '{SEC_HEADER}'.")

    content = pre.get_text()
    blocks = re.split(r"\nFeature Key\s+", content)[2:]  # 最初の例などは無視

    features: List[Feature] = []
    for block in blocks:
        block = "Feature Key           " + block.strip()
        lines = block.splitlines()

        header_indices = OrderedDict()
        for i, line in enumerate(lines):
            if line.strip() and not re.match(r"^\s", line):
                parts = re.split(r"\s{2,}", line.strip(), maxsplit=1)
                if not parts:
                    continue
                header = parts[0].strip().lower()
                if header in COL_HEADERS:
                    header_indices[header] = i

        headers = list(header_indices)
        section_map: dict[str, str | List[str]] = {}

        for i, header in enumerate(headers):
            start = header_indices[header]
            end = header_indices[headers[i + 1]] if i + 1 < len(headers) else len(lines)
            section_lines = lines[start:end]
            section_map[header] = _parse_section_lines(header, section_lines)

        if "feature key" not in section_map or "definition" not in section_map:
            raise ValueError("Feature Key or Definition not found in section.")

        feature = Feature(
            feature_key=section_map["feature key"],  # type: ignore
            definition=section_map["definition"],  # type: ignore
            mandatory_qualifiers=section_map.get("mandatory qualifiers", []),  # type: ignore
            optional_qualifiers=section_map.get("optional qualifiers", []),  # type: ignore
            organism_scope=section_map.get("organism scope"),  # type: ignore
            molecule_scope=section_map.get("molecule scope"),  # type: ignore
            references=section_map.get("references"),  # type: ignore
            comment=section_map.get("comment"),  # type: ignore
            example=section_map.get("example"),  # type: ignore
        )
        features.append(feature)

    return features


def dump_full_features(features: List[Feature]) -> None:
    feature_table_dir_path = get_feature_table_dir_path()

    features_full_path = feature_table_dir_path.joinpath("features_full.json")
    with features_full_path.open("w", encoding="utf-8") as file:
        json.dump([feature.model_dump() for feature in features], file, indent=2, ensure_ascii=False)


class FeatureSummary(BaseModel):
    feature_key: str
    mandatory_qualifiers: List[str]
    optional_qualifiers: List[str]


def to_features_summary(features: List[Feature]) -> List[FeatureSummary]:
   def _parse_keys(lines: List[str]) -> List[str]:
        keys = []
        for line in lines:
            if not line.startswith("/"):
                continue
            match = re.match(r'^/?([a-zA-Z0-9_]+)', line.strip())
            if match:
                keys.append(match.group(1))
        return keys

    features_summary = []
    for feature in features:
        features_summary.append({
            "feature_key": feature.feature_key,
            "mandatory_qualifiers": _parse_keys(feature.mandatory_qualifiers),
            "optional_qualifiers": _parse_keys(feature.optional_qualifiers),
        })

    return features_summary



class Qualifier(BaseModel):
    qualifier_key: str = Field(
        ...,
        description="The qualifier key name",
    )
    definition: str = Field(
        ...,
        description="The definition of the key",
    )
    value_format: str = Field(
        ...,
        description="Format of the value, if required",
    )
    example: List[str] = Field(
        ...,
        description="Example of the qualifier with value",
    )
    comment: Optional[str] = Field(
        None,
        description="Comments and clarifications",
    )


def extract_qualifiers_from_html(html: str) -> List[Qualifier]:
    SEC_HEADER = "7.3.1 Qualifier List"

    soup = BeautifulSoup(html, "lxml")
    h3 = soup.find("h3", string=lambda t: t and SEC_HEADER in t)
    if not h3:
        raise ValueError(f"Header '{SEC_HEADER}' not found.")

    pre = h3.find_next_sibling("pre")
    if not pre:
        raise ValueError(f"<pre> tag not found after '{SEC_HEADER}'.")

    content = pre.get_text()
    blocks = re.split(r"\nQualifier\s+", content)[2:]

    qualifiers = []
    for block in blocks:
        block = "Qualifier       " + block.strip()
        lines = block.splitlines()

        # header extraction
        header_indices = OrderedDict()
        for i, line in enumerate(lines):
            if not line.strip() or re.match(r"^[ \t]", line):
                continue
            parts = re.split(r"\s{2,}", line.strip(), maxsplit=1)
            if parts:
                key = parts[0].strip().lower().replace("comments", "comment").replace("examples", "example")
                header_indices[key] = i

        section_map = {}
        headers = list(header_indices.keys())
        for i, header in enumerate(headers):
            start = header_indices[header]
            end = header_indices[headers[i + 1]] if i + 1 < len(headers) else len(lines)
            section_lines = lines[start:end]
            section_lines[0] = section_lines[0][len(header):].strip()
            section_lines = [line.strip() for line in section_lines if line.strip()]
            section_map[header] = "\n".join(section_lines)

        if "qualifier" not in section_map or "definition" not in section_map:
            continue  # skip malformed

        qualifier_key = section_map["qualifier"].lstrip("/").rstrip("=").strip()
        example_lines = section_map.get("example", "").split("\n") if "example" in section_map else []

        qualifiers.append(Qualifier(
            qualifier_key=qualifier_key,
            definition=section_map["definition"],
            value_format=section_map.get("value format", ""),
            example=example_lines,
            comment=section_map.get("comment")
        ))

    return qualifiers


def qualifier_to_jsonschema(qualifier: Qualifier) -> Dict[str, Dict]:
    desc = qualifier.definition.strip()
    if qualifier.comment:
        desc += f" Comment: {qualifier.comment.strip()}"

    schema = {
        qualifier.qualifier_key: {
            "type": "string",  # default
            "description": desc
        }
    }

    examples = []

    if qualifier.value_format == '"text"':
        current = ""
        for line in qualifier.example:
            if line.startswith("/"):
                if current:
                    examples.append(current.strip())
                parts = line.split("=", maxsplit=1)
                if len(parts) > 1:
                    current = parts[1].strip()
            else:
                current += " " + line.strip()
        if current:
            examples.append(current.strip())
        examples = [html.unescape(e).replace('"', '') for e in examples]

    elif qualifier.value_format == "none":
        schema[qualifier.qualifier_key]["type"] = "null"

    overrides = {
        "anticodon": {
            "examples": [
                "(pos:34..36,aa:Phe,seq:aaa)",
                "(pos:join(5,495..496),aa:Leu,seq:taa)",
                "(pos:complement(4156..4158),aa:Gln,seq:ttg)"
            ]
        },
        "artificial_location": {
            "enum": [
                "heterogeneous population sequenced",
                "low-quality sequence region"
            ]
        },
        "bio_material": {
            "examples": ["CGC:CB3912"]
        },
        "citation": {
            "examples": ["[3]"]
        },
        "function": {
            "examples": ["essential for recognition of cofactor"]
        },
        "gene_synonym": {
            "examples": ["Hox-3.3"]
        },
        "sex": {
            "examples": [e.replace("[", "(").replace("]", ")") for e in examples]
        },
    }

    if qualifier.qualifier_key in overrides:
        for k, v in overrides[qualifier.qualifier_key].items():
            schema[qualifier.qualifier_key][k] = v
    elif examples:
        schema[qualifier.qualifier_key]["examples"] = examples

    return schema


def main() -> None:
    feature_table_html = fetch_feature_table_html()
    features = extract_features_from_html(feature_table_html)
    dump_features(features)
    qualifiers = extract_qualifiers_from_html(feature_table_html)
    qualifiers_json_path = get_feature_table_dir_path().joinpath("qualifiers.json")
    with qualifiers_json_path.open("w", encoding="utf-8") as file:
        json.dump([qualifier.model_dump() for qualifier in qualifiers], file, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
