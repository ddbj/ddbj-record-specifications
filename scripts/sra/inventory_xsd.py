# /// script
# requires-python = ">=3.10"
# dependencies = ["xmlschema"]
# ///
"""List every element and attribute path each SRA XSD version allows, per document type.

The first of the three steps that produce docs/v3-sra-mapping.yml (see scripts/sra/README.md).

Usage:
    uv run scripts/sra/inventory_xsd.py XSD_DIR OUT.json

XSD_DIR is the directory holding one subdirectory per version (SRA.1.5d2, ..., SRA.1.6.1),
as in D-way's dracommon (generator/xjc/xsd/SRA.1.0).

For each path the output records the versions it appears in, whether it holds text, its
enumeration if any, and whether it can repeat under one parent (directly through maxOccurs,
or because an enclosing sequence or choice repeats).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import xmlschema
from xmlschema.validators import XsdGroup

DOCS = {
    "submission": ("SRA.submission.xsd", "SUBMISSION"),
    "study": ("SRA.study.xsd", "STUDY"),
    "sample": ("SRA.sample.xsd", "SAMPLE"),
    "experiment": ("SRA.experiment.xsd", "EXPERIMENT"),
    "run": ("SRA.run.xsd", "RUN"),
    "analysis": ("SRA.analysis.xsd", "ANALYSIS"),
}

# Oldest first, the order they were in force. The names do not sort (1.5d2, 1.5e and 1.5e2
# came before 1.5.7), so the order is written out.
VERSIONS = ["SRA.1.5d2", "SRA.1.5e", "SRA.1.5e2", "SRA.1.5.7", "SRA.1.5.8", "SRA.1.5.9", "SRA.1.6.0", "SRA.1.6.1"]


def _repeats(group: Any) -> bool:
    return group.max_occurs is None or group.max_occurs > 1


def _in_repeating_group(content: Any, child: Any) -> bool:
    """Whether a model group between the parent and this child repeats."""
    if content is None or not hasattr(content, "iter_model"):
        return False

    def search(group: Any, repeating: bool) -> bool | None:
        for item in group:
            if item is child:
                return repeating
            if isinstance(item, XsdGroup):
                found = search(item, repeating or _repeats(item))
                if found is not None:
                    return found
        return None

    return bool(search(content, _repeats(content)))


def walk(  # noqa: PLR0913
    element: Any, path: str, out: dict[str, Any], version: str, seen: frozenset[int], *, many: bool = False
) -> None:
    entry = out.setdefault(path, {"versions": set(), "text": False, "enum": set(), "many": False})
    entry["versions"].add(version)

    if many or _repeats(element):
        entry["many"] = True

    tp = element.type
    if tp.is_simple() or tp.has_simple_content() or getattr(tp, "mixed", False):
        entry["text"] = True
        base = getattr(tp, "base_type", None)
        enumeration = getattr(tp, "enumeration", None) or (base is not None and getattr(base, "enumeration", None))
        if enumeration:
            entry["enum"].update(str(value) for value in enumeration)

    for name, attribute in (element.attributes or {}).items():
        if name is None:
            continue
        attr_entry = out.setdefault(
            f"{path}/@{attribute.local_name}", {"versions": set(), "text": True, "enum": set(), "many": False}
        )
        attr_entry["versions"].add(version)
        if getattr(attribute.type, "enumeration", None):
            attr_entry["enum"].update(str(value) for value in attribute.type.enumeration)

    # A type that contains itself: stop, and say so.
    if id(tp) in seen:
        entry["recursive"] = True
        return

    content = getattr(tp, "content", None)
    for child in element.iterchildren():
        if child.local_name is None:
            continue
        walk(
            child,
            f"{path}/{child.local_name}",
            out,
            version,
            seen | {id(tp)},
            many=_in_repeating_group(content, child),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("xsd_dir", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()

    unknown = {path.name for path in args.xsd_dir.iterdir() if path.is_dir()} - set(VERSIONS)
    if unknown:
        parser.error(f"versions not in VERSIONS: {sorted(unknown)}. Add them there, in the order they came into force.")

    result: dict[str, dict[str, Any]] = {doc: {} for doc in DOCS}

    for version in VERSIONS:
        for doc, (xsd, root) in DOCS.items():
            path = args.xsd_dir / version / xsd
            if not path.exists():
                continue
            schema = xmlschema.XMLSchema(str(path), validation="lax")
            walk(schema.elements[root], root, result[doc], version, frozenset())

    inventory = {
        doc: {
            path: {
                "versions": [v for v in VERSIONS if v in entry["versions"]],
                "text": entry["text"],
                "enum": sorted(entry["enum"]),
                "many": entry["many"],
                **({"recursive": True} if entry.get("recursive") else {}),
            }
            for path, entry in sorted(paths.items())
        }
        for doc, paths in result.items()
    }

    args.out.write_text(json.dumps(inventory, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
