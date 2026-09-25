# /// script
# requires-python = ">=3.10"
# dependencies = ["pydantic", "pyyaml"]
# ///
"""Write docs/v3-sra-mapping.yml: where in v3 each SRA XML element and attribute goes.

The last of the three steps (see scripts/sra/README.md).

Usage:
    uv run scripts/sra/build_mapping.py INVENTORY.json CENSUS.json docs/v3-sra-mapping.yml

INVENTORY.json comes from inventory_xsd.py and CENSUS.json from census_drmdb.rb. Every path in
either must have a rule here, and the rules must agree with what the XSDs and the stored
documents say about each path: a container holds no text, an element that repeats goes into a
list, and a value typed int / float / bool in v3 never held anything else. The script lists what
fails and writes nothing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from types import NoneType, UnionType
from typing import Any, Union, get_args, get_origin, get_type_hints

import yaml
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ddbj_record.schema.v3 import DdbjRecord

# Document type -> (root element, where it goes in v3).
ENTITIES = {
    "submission": ("SUBMISSION", "submission"),
    "study": ("STUDY", "project"),
    "sample": ("SAMPLE", "samples[]"),
    "experiment": ("EXPERIMENT", "experiments[]"),
    "run": ("RUN", "runs[]"),
    "analysis": ("ANALYSIS", "analyses[]"),
}

CONTAINER = "(container)"
NAME_IS_VALUE = " (要素名が値)"
LOWER_NAME_IS_VALUE = " (要素名を小文字にした値)"

IDENTIFIER_TYPES = {
    "PRIMARY_ID": "primary",
    "SECONDARY_ID": "secondary",
    "EXTERNAL_ID": "external",
    "SUBMITTER_ID": "submitter",
    "UUID": "uuid",
}

ATTRIBUTE_FIELDS = {"TAG": "name", "VALUE": "value", "UNITS": "unit"}

# Reference elements (SRA's RefObjectType) and where the target of each goes: a relation, or
# a field of the object that holds the reference together with other values.
REFERENCES = {
    "EXPERIMENT/STUDY_REF": "relations[part_of project].target",
    "ANALYSIS/STUDY_REF": "relations[part_of project].target",
    "EXPERIMENT/DESIGN/SAMPLE_DESCRIPTOR": "relations[part_of sample].target",
    "RUN/EXPERIMENT_REF": "relations[part_of experiment].target",
    "ANALYSIS/TARGETS/TARGET": "relations[derived_from].target",
    "EXPERIMENT/DESIGN/SAMPLE_DESCRIPTOR/POOL/MEMBER": "experiments[].pool.members[].sample",
    "EXPERIMENT/DESIGN/SAMPLE_DESCRIPTOR/POOL/DEFAULT_MEMBER": "experiments[].pool.default_member.sample",
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/RUN_LABELS/RUN": "analyses[].reference_alignment.run_labels[].run",
}

REFERENCE_ATTRIBUTES = {"@accession": "accession", "@refname": "id", "@refcenter": "center_name"}

# Paths that follow no pattern below.
EXPLICIT = {
    # submission
    "SUBMISSION/TITLE": "submission.title",
    "SUBMISSION/@lab_name": "submission.sra.lab_name",
    "SUBMISSION/@submission_comment": "submission.sra.submission_comment",
    "SUBMISSION/@submission_date": "submission.sra.submission_date",
    "SUBMISSION/CONTACTS": CONTAINER,
    "SUBMISSION/CONTACTS/CONTACT": "submission.sra.contacts[]",
    "SUBMISSION/CONTACTS/CONTACT/@name": "submission.sra.contacts[].name",
    "SUBMISSION/CONTACTS/CONTACT/@inform_on_status": "submission.sra.contacts[].inform_on_status",
    "SUBMISSION/CONTACTS/CONTACT/@inform_on_error": "submission.sra.contacts[].inform_on_error",
    "SUBMISSION/ACTIONS": CONTAINER,
    "SUBMISSION/ACTIONS/ACTION": "submission.sra.actions[]",
    # study
    "STUDY/DESCRIPTOR": CONTAINER,
    "STUDY/DESCRIPTOR/STUDY_TITLE": "project.title",
    "STUDY/DESCRIPTOR/STUDY_ABSTRACT": "project.description",
    "STUDY/DESCRIPTOR/STUDY_DESCRIPTION": "project.study_description",
    "STUDY/DESCRIPTOR/CENTER_PROJECT_NAME": "project.center_project_name",
    "STUDY/DESCRIPTOR/CENTER_NAME": "project.descriptor_center_name",
    "STUDY/DESCRIPTOR/STUDY_TYPE": CONTAINER,
    "STUDY/DESCRIPTOR/STUDY_TYPE/@existing_study_type": "project.study_types[]",
    "STUDY/DESCRIPTOR/STUDY_TYPE/@new_study_type": "project.new_study_type",
    "STUDY/DESCRIPTOR/RELATED_STUDIES": CONTAINER,
    "STUDY/DESCRIPTOR/RELATED_STUDIES/RELATED_STUDY": "relations[related_to]",
    "STUDY/DESCRIPTOR/RELATED_STUDIES/RELATED_STUDY/IS_PRIMARY": "relations[related_to].properties{is_primary}",
    "STUDY/DESCRIPTOR/RELATED_STUDIES/RELATED_STUDY/RELATED_LINK": CONTAINER,
    "STUDY/DESCRIPTOR/RELATED_STUDIES/RELATED_STUDY/RELATED_LINK/DB": "relations[related_to].target.db",
    "STUDY/DESCRIPTOR/RELATED_STUDIES/RELATED_STUDY/RELATED_LINK/ID": "relations[related_to].target.id",
    "STUDY/DESCRIPTOR/RELATED_STUDIES/RELATED_STUDY/RELATED_LINK/LABEL": "relations[related_to].label",
    # sample
    "SAMPLE/TITLE": "samples[].title",
    "SAMPLE/DESCRIPTION": "samples[].description",
    "SAMPLE/SAMPLE_NAME": CONTAINER,
    "SAMPLE/SAMPLE_NAME/TAXON_ID": "samples[].organism.taxonomy_id",
    "SAMPLE/SAMPLE_NAME/SCIENTIFIC_NAME": "samples[].organism.name",
    "SAMPLE/SAMPLE_NAME/COMMON_NAME": "samples[].organism.common_name",
    "SAMPLE/SAMPLE_NAME/ANONYMIZED_NAME": "samples[].anonymized_name",
    "SAMPLE/SAMPLE_NAME/INDIVIDUAL_NAME": "samples[].individual_name",
    # experiment
    "EXPERIMENT/TITLE": "experiments[].title",
    "EXPERIMENT/DESIGN": CONTAINER,
    "EXPERIMENT/DESIGN/DESIGN_DESCRIPTION": "experiments[].description",
    "EXPERIMENT/DESIGN/LIBRARY_DESCRIPTOR": "experiments[].library",
    "EXPERIMENT/DESIGN/LIBRARY_DESCRIPTOR/LIBRARY_NAME": "experiments[].library.name",
    "EXPERIMENT/DESIGN/LIBRARY_DESCRIPTOR/LIBRARY_STRATEGY": "experiments[].library.strategy",
    "EXPERIMENT/DESIGN/LIBRARY_DESCRIPTOR/LIBRARY_SOURCE": "experiments[].library.source",
    "EXPERIMENT/DESIGN/LIBRARY_DESCRIPTOR/LIBRARY_SELECTION": "experiments[].library.selection",
    "EXPERIMENT/DESIGN/LIBRARY_DESCRIPTOR/LIBRARY_CONSTRUCTION_PROTOCOL": "experiments[].library.construction_protocol",
    "EXPERIMENT/DESIGN/LIBRARY_DESCRIPTOR/POOLING_STRATEGY": "experiments[].library.pooling_strategy",
    "EXPERIMENT/DESIGN/LIBRARY_DESCRIPTOR/LIBRARY_LAYOUT": CONTAINER,
    "EXPERIMENT/DESIGN/LIBRARY_DESCRIPTOR/LIBRARY_LAYOUT/SINGLE": "experiments[].library.layout" + LOWER_NAME_IS_VALUE,
    "EXPERIMENT/DESIGN/LIBRARY_DESCRIPTOR/LIBRARY_LAYOUT/PAIRED": "experiments[].library.layout" + LOWER_NAME_IS_VALUE,
    "EXPERIMENT/DESIGN/LIBRARY_DESCRIPTOR/LIBRARY_LAYOUT/PAIRED/@NOMINAL_LENGTH": "experiments[].library.nominal_length",
    "EXPERIMENT/DESIGN/LIBRARY_DESCRIPTOR/LIBRARY_LAYOUT/PAIRED/@NOMINAL_SDEV": "experiments[].library.nominal_sdev",
    "EXPERIMENT/DESIGN/LIBRARY_DESCRIPTOR/TARGETED_LOCI": CONTAINER,
    "EXPERIMENT/DESIGN/LIBRARY_DESCRIPTOR/TARGETED_LOCI/LOCUS": "experiments[].targeted_loci[]",
    "EXPERIMENT/DESIGN/LIBRARY_DESCRIPTOR/TARGETED_LOCI/LOCUS/@locus_name": "experiments[].targeted_loci[].name",
    "EXPERIMENT/DESIGN/LIBRARY_DESCRIPTOR/TARGETED_LOCI/LOCUS/@description": "experiments[].targeted_loci[].description",
    "EXPERIMENT/DESIGN/LIBRARY_DESCRIPTOR/TARGETED_LOCI/LOCUS/PROBE_SET": "experiments[].targeted_loci[].probe_set",
    "EXPERIMENT/DESIGN/LIBRARY_DESCRIPTOR/TARGETED_LOCI/LOCUS/PROBE_SET/DB": "experiments[].targeted_loci[].probe_set.db",
    "EXPERIMENT/DESIGN/LIBRARY_DESCRIPTOR/TARGETED_LOCI/LOCUS/PROBE_SET/ID": "experiments[].targeted_loci[].probe_set.id",
    "EXPERIMENT/DESIGN/LIBRARY_DESCRIPTOR/TARGETED_LOCI/LOCUS/PROBE_SET/LABEL": "experiments[].targeted_loci[].probe_set.label",
    "EXPERIMENT/DESIGN/SAMPLE_DESCRIPTOR/POOL": "experiments[].pool",
    "EXPERIMENT/PROCESSING": CONTAINER,
    "EXPERIMENT/PROCESSING/PIPELINE": CONTAINER,
    "EXPERIMENT/PROCESSING/DIRECTIVES": CONTAINER,
    "EXPERIMENT/PROCESSING/DIRECTIVES/SAMPLE_DEMUX_DIRECTIVE": "experiments[].sample_demux_directive",
    # run
    "RUN/TITLE": "runs[].title",
    "RUN/@run_date": "runs[].run_date",
    "RUN/@run_center": "runs[].run_center",
    "RUN/PROCESSING": CONTAINER,
    "RUN/PROCESSING/PIPELINE": CONTAINER,
    "RUN/PROCESSING/DIRECTIVES": CONTAINER,
    "RUN/PROCESSING/DIRECTIVES/SAMPLE_DEMUX_DIRECTIVE": "runs[].sample_demux_directive",
    # analysis
    "ANALYSIS/TITLE": "analyses[].title",
    "ANALYSIS/DESCRIPTION": "analyses[].description",
    "ANALYSIS/@analysis_date": "analyses[].analysis_date",
    "ANALYSIS/@analysis_center": "analyses[].analysis_center",
    "ANALYSIS/ANALYSIS_TYPE": CONTAINER,
    "ANALYSIS/TARGETS": CONTAINER,
    "ANALYSIS/TARGETS/TARGET/@sra_object_type": "relations[derived_from].target.db",
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/ASSEMBLY": CONTAINER,
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/ASSEMBLY/STANDARD": "analyses[].reference_alignment.standard_assembly",
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/ASSEMBLY/STANDARD/@short_name": (
        "analyses[].reference_alignment.standard_assembly.short_name"
    ),
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/ASSEMBLY/STANDARD/NAME": "analyses[].reference_alignment.standard_assembly.names[]",
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/ASSEMBLY/STANDARD/NAME/DB": (
        "analyses[].reference_alignment.standard_assembly.names[].db"
    ),
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/ASSEMBLY/STANDARD/NAME/ID": (
        "analyses[].reference_alignment.standard_assembly.names[].id"
    ),
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/ASSEMBLY/STANDARD/NAME/LABEL": (
        "analyses[].reference_alignment.standard_assembly.names[].label"
    ),
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/ASSEMBLY/CUSTOM": "analyses[].reference_alignment.custom_assembly",
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/ASSEMBLY/CUSTOM/DESCRIPTION": (
        "analyses[].reference_alignment.custom_assembly.description"
    ),
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/ASSEMBLY/CUSTOM/REFERENCE_SOURCE": (
        "analyses[].reference_alignment.custom_assembly.sources[]"
    ),
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/ASSEMBLY/CUSTOM/REFERENCE_SOURCE/URL_LINK": CONTAINER,
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/ASSEMBLY/CUSTOM/REFERENCE_SOURCE/URL_LINK/URL": (
        "analyses[].reference_alignment.custom_assembly.sources[].url"
    ),
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/ASSEMBLY/CUSTOM/REFERENCE_SOURCE/URL_LINK/LABEL": (
        "analyses[].reference_alignment.custom_assembly.sources[].label"
    ),
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/ASSEMBLY/CUSTOM/REFERENCE_SOURCE/XREF_LINK": CONTAINER,
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/ASSEMBLY/CUSTOM/REFERENCE_SOURCE/XREF_LINK/DB": (
        "analyses[].reference_alignment.custom_assembly.sources[].db"
    ),
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/ASSEMBLY/CUSTOM/REFERENCE_SOURCE/XREF_LINK/ID": (
        "analyses[].reference_alignment.custom_assembly.sources[].id"
    ),
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/ASSEMBLY/CUSTOM/REFERENCE_SOURCE/XREF_LINK/LABEL": (
        "analyses[].reference_alignment.custom_assembly.sources[].label"
    ),
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/PROCESSING/DIRECTIVES": CONTAINER,
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/PROCESSING/DIRECTIVES/alignment_includes_unaligned_reads": (
        "analyses[].reference_alignment.includes_unaligned_reads"
    ),
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/PROCESSING/DIRECTIVES/alignment_marks_duplicate_reads": (
        "analyses[].reference_alignment.marks_duplicate_reads"
    ),
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/PROCESSING/DIRECTIVES/alignment_includes_failed_reads": (
        "analyses[].reference_alignment.includes_failed_reads"
    ),
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/RUN_LABELS": CONTAINER,
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/RUN_LABELS/RUN/@data_block_name": (
        "analyses[].reference_alignment.run_labels[].data_block_name"
    ),
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/RUN_LABELS/RUN/@read_group_label": (
        "analyses[].reference_alignment.run_labels[].read_group_label"
    ),
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/SEQ_LABELS": CONTAINER,
    "ANALYSIS/ANALYSIS_TYPE/REFERENCE_ALIGNMENT/SEQ_LABELS/SEQUENCE": "analyses[].reference_alignment.seq_labels[]",
    # In no XSD: from registrations made before SRA XSD 1.5, found only in D-way's documents.
    "SUBMISSION/@submission_id": "submission.sra.legacy.submission_id",
    "SUBMISSION/FILES": CONTAINER,
    "SUBMISSION/FILES/FILE": "submission.sra.legacy.files[]",
    "STUDY/DESCRIPTOR/PROJECT_ID": "project.legacy.project_id",
    "EXPERIMENT/@expected_number_runs": "experiments[].legacy.expected_number_runs",
    "EXPERIMENT/DESIGN/LIBRARY_DESCRIPTOR/LIBRARY_LAYOUT/PAIRED/@ORIENTATION": "experiments[].library.legacy.orientation",
    "EXPERIMENT/DESIGN/GAP_DESCRIPTOR": CONTAINER,
    "EXPERIMENT/DESIGN/GAP_DESCRIPTOR/GAP": "experiments[].legacy.gaps[]",
    "EXPERIMENT/DESIGN/GAP_DESCRIPTOR/GAP/GAP_SPEC": CONTAINER,
    "EXPERIMENT/DESIGN/GAP_DESCRIPTOR/GAP/GAP_SPEC/@link3": "experiments[].legacy.gaps[].link3",
    "EXPERIMENT/DESIGN/GAP_DESCRIPTOR/GAP/GAP_SPEC/@link5": "experiments[].legacy.gaps[].link5",
    "EXPERIMENT/DESIGN/GAP_DESCRIPTOR/GAP/GAP_SPEC/interval": CONTAINER,
    "EXPERIMENT/DESIGN/GAP_DESCRIPTOR/GAP/GAP_SPEC/interval/@min_length": "experiments[].legacy.gaps[].min_length",
    "EXPERIMENT/DESIGN/GAP_DESCRIPTOR/GAP/GAP_SPEC/interval/@max_length": "experiments[].legacy.gaps[].max_length",
    "EXPERIMENT/DESIGN/GAP_DESCRIPTOR/GAP/GAP_SPEC/statistic": CONTAINER,
    "EXPERIMENT/DESIGN/GAP_DESCRIPTOR/GAP/GAP_SPEC/statistic/@mean": "experiments[].legacy.gaps[].mean",
    "EXPERIMENT/DESIGN/GAP_DESCRIPTOR/GAP/GAP_SPEC/statistic/@stdev": "experiments[].legacy.gaps[].stdev",
    "EXPERIMENT/DESIGN/GAP_DESCRIPTOR/GAP/GAP_TYPE": CONTAINER,
    "EXPERIMENT/PROCESSING/BASE_CALLS": "experiments[].legacy.base_calling",
    "EXPERIMENT/PROCESSING/BASE_CALLS/BASE_CALLER": "experiments[].legacy.base_calling.base_caller",
    "EXPERIMENT/PROCESSING/BASE_CALLS/SEQUENCE_SPACE": "experiments[].legacy.base_calling.sequence_space",
    "EXPERIMENT/PROCESSING/QUALITY_SCORES": "experiments[].legacy.quality_scoring[]",
    "EXPERIMENT/PROCESSING/QUALITY_SCORES/@qtype": "experiments[].legacy.quality_scoring[].qtype",
    "EXPERIMENT/PROCESSING/QUALITY_SCORES/QUALITY_SCORER": "experiments[].legacy.quality_scoring[].quality_scorer",
    "EXPERIMENT/PROCESSING/QUALITY_SCORES/NUMBER_OF_LEVELS": "experiments[].legacy.quality_scoring[].number_of_levels",
    "EXPERIMENT/PROCESSING/QUALITY_SCORES/MULTIPLIER": "experiments[].legacy.quality_scoring[].multiplier",
    "RUN/@instrument_model": "runs[].legacy.instrument_model",
    "RUN/@instrument_name": "runs[].legacy.instrument_name",
    "RUN/@run_file": "runs[].legacy.run_file",
    "RUN/@total_data_blocks": "runs[].legacy.total_data_blocks",
}

# Paths that only exist because a stored document is not well-formed (a <SAMPLE_ATTRIBUTE>
# start tag is missing), as the parser recovered it.
MALFORMED = {
    "SAMPLE/SAMPLE_ATTRIBUTE",
    "SAMPLE/SAMPLE_ATTRIBUTE/TAG",
    "SAMPLE/SAMPLE_ATTRIBUTE/VALUE",
    "SAMPLE/SAMPLE_ATTRIBUTE/UNITS",
    "SAMPLE/SAMPLE_ATTRIBUTES/TAG",
    "SAMPLE/SAMPLE_ATTRIBUTES/VALUE",
    "SAMPLE/SAMPLE_ATTRIBUTES/UNITS",
}

READ_SPEC_FIELDS = {
    "READ_INDEX": "read_index",
    "READ_LABEL": "read_label",
    "READ_CLASS": "read_class",
    "READ_TYPE": "read_type",
    "BASE_COORD": "base_coord",
    "RELATIVE_ORDER": "relative_order",
    "RELATIVE_ORDER/@follows_read_index": "relative_order.follows_read_index",
    "RELATIVE_ORDER/@precedes_read_index": "relative_order.precedes_read_index",
    "EXPECTED_BASECALL_TABLE": "expected_basecall_table",
    "EXPECTED_BASECALL_TABLE/@base_coord": "expected_basecall_table.base_coord",
    "EXPECTED_BASECALL_TABLE/@default_length": "expected_basecall_table.default_length",
    "EXPECTED_BASECALL_TABLE/BASECALL": "expected_basecall_table.basecalls[].value",
    "CYCLE_COORD": "legacy.cycle_coord",
    "EXPECTED_BASECALL": "legacy.expected_basecall.value",
    "EXPECTED_BASECALL/@base_coord": "legacy.expected_basecall.base_coord",
    "EXPECTED_BASECALL/@default_length": "legacy.expected_basecall.default_length",
}

PIPE_SECTION_FIELDS = {
    "@section_name": "section_name",
    "NOTES": "notes",
    "PREV_STEP_INDEX": "prev_step_indexes[]",
    "PROGRAM": "program",
    "STEP_INDEX": "step_index",
    "VERSION": "version",
}

LINK_RELATIONS = {"URL_LINK": "reference", "XREF_LINK": "xref", "ENTREZ_LINK": "xref", "DDBJ_LINK": "xref"}
LINK_FIELDS = {
    "URL": "target.url",
    "DB": "target.db",
    "ID": "target.id",
    "LABEL": "label",
    "QUERY": "properties{query}",
}

POOL_MEMBER_FIELDS = {
    "@member_name": "member_name",
    "@proportion": "proportion",
    "READ_LABEL": "read_labels[].value",
    "READ_LABEL/@read_group_tag": "read_labels[].read_group_tag",
}


def identifiers(base: str, below: str) -> str | None:
    """The location of a path below an IDENTIFIERS element, on the object at base."""
    if not below:
        return CONTAINER
    head, _, tail = below.partition("/")
    kind = IDENTIFIER_TYPES.get(head)
    return kind and f"{base}.identifiers[{kind}].{tail.lstrip('@') or 'value'}"


def reference(path: str) -> str | None:
    """The location of a path in or below a reference element, if it is one."""
    for ref, target in sorted(REFERENCES.items(), key=lambda item: -len(item[0])):
        if path != ref and not path.startswith(ref + "/"):
            continue
        below = path[len(ref) + 1 :]
        if not below:
            # The element itself is the relation, or the object holding the reference.
            return target.rsplit(".", 1)[0]
        if below in REFERENCE_ATTRIBUTES:
            return f"{target}.{REFERENCE_ATTRIBUTES[below]}"
        if below.startswith("IDENTIFIERS"):
            return identifiers(target, below[len("IDENTIFIERS") + 1 :])
        return None
    return None


def spot_descriptor(entity: str, below: str | None) -> str | None:
    base = f"{entity}.spot_descriptor"
    if below is None:
        return base
    fixed = {
        "SPOT_DECODE_SPEC": CONTAINER,
        "SPOT_DECODE_SPEC/SPOT_LENGTH": f"{base}.spot_length",
        "SPOT_DECODE_SPEC/NUMBER_OF_READS_PER_SPOT": f"{base}.legacy.number_of_reads_per_spot",
        "SPOT_DECODE_SPEC/ADAPTER_SPEC": f"{base}.legacy.adapter_spec",
        "SPOT_DECODE_SPEC/READ_SPEC": f"{base}.reads[]",
    }
    if below in fixed:
        return fixed[below]
    leaf = below.removeprefix("SPOT_DECODE_SPEC/READ_SPEC/")
    if leaf in READ_SPEC_FIELDS:
        return f"{base}.reads[].{READ_SPEC_FIELDS[leaf]}"
    m = re.fullmatch(r"EXPECTED_BASECALL_TABLE/BASECALL/@(\w+)", leaf)
    return m and f"{base}.reads[].expected_basecall_table.basecalls[].{m.group(1)}"


def data_block(entity: str, below: str | None) -> str | None:
    base = f"{entity}.data_blocks[]"
    fixed = {
        None: base,
        "FILES": CONTAINER,
        "FILES/FILE": f"{base}.files[]",
        "FILES/FILE/READ_LABEL": f"{base}.files[].read_labels[]",
        "FILES/FILE/DATA_SERIES_LABEL": f"{base}.files[].legacy.data_series_labels[]",
    }
    if below in fixed:
        return fixed[below]
    if m := re.fullmatch(r"FILES/FILE/@(\w+)", below or ""):
        return f"{base}.files[].{m.group(1)}"
    if m := re.fullmatch(r"@(\w+)", below or ""):
        # ANALYSIS names it @member. Only name, serial and member_name are in a current XSD.
        attribute = {"member": "member_name"}.get(m.group(1), m.group(1))
        return f"{base}.{attribute}" if attribute in ("name", "serial", "member_name") else f"{base}.legacy.{attribute}"
    return None


def platform(entity: str, below: str | None) -> str:
    if below is None:
        return f"{entity}.platform"
    _vendor, _, leaf = below.partition("/")
    if not leaf:
        return f"{entity}.platform.type" + NAME_IS_VALUE
    if leaf == "INSTRUMENT_MODEL":
        return f"{entity}.platform.instrument_model"
    if leaf == "COLOR_MATRIX":
        return CONTAINER
    if leaf == "COLOR_MATRIX/COLOR":
        return f"{entity}.platform.legacy.color_matrix[].color"
    if leaf == "COLOR_MATRIX/COLOR/@dibase":
        return f"{entity}.platform.legacy.color_matrix[].dibase"
    return f"{entity}.platform.legacy.{leaf.lower()}"


def link(rel: str) -> str | None:
    m = re.fullmatch(r"(\w+)_LINKS(?:/\1_LINK(?:/(\w+)(?:/(\w+))?)?)?", rel)
    if not m:
        return None
    kind, leaf = m.group(2), m.group(3)
    if rel == f"{m.group(1)}_LINKS":
        return CONTAINER
    if kind is None:
        return "relations[]"
    relation = LINK_RELATIONS.get(kind)
    if relation is None:
        return None
    if leaf is None:
        if kind in ("ENTREZ_LINK", "DDBJ_LINK"):
            return f'relations[{relation}].properties{{sra_link_type}} ({kind} なら "{kind.removesuffix("_LINK").lower()}")'
        return f"relations[{relation}]"
    field = LINK_FIELDS.get(leaf)
    return field and f"relations[{relation}].{field}"


def rule(doc: str, path: str) -> str | None:
    """Where in v3 the element or attribute at path goes, or None if no rule covers it."""
    root, entity = ENTITIES[doc]

    if path == root:
        return entity if entity.endswith("[]") else CONTAINER
    if not path.startswith(root + "/"):
        return None

    rel = path[len(root) + 1 :]
    if path in EXPLICIT:
        return EXPLICIT[path]
    if (location := reference(path)) is not None:
        return location

    if m := re.fullmatch(r"IDENTIFIERS(?:/(.*))?", rel):
        return identifiers(entity, m.group(1) or "")
    if rel in ("@accession", "@alias", "@center_name", "@broker_name"):
        return f"{entity}.{rel[1:]}"

    if m := re.fullmatch(r"(\w+)_ATTRIBUTES(/\1_ATTRIBUTE(?:/(TAG|VALUE|UNITS))?)?", rel):
        if m.group(2) is None:
            return CONTAINER
        return f"{entity}.attributes[]" + (f".{ATTRIBUTE_FIELDS[m.group(3)]}" if m.group(3) else "")
    if path in MALFORMED:
        leaf = path.rsplit("/", 1)[-1]
        return f"{entity}.attributes[]" + (f".{ATTRIBUTE_FIELDS[leaf]}" if leaf in ATTRIBUTE_FIELDS else "")

    if (location := link(rel)) is not None:
        return location

    if m := re.fullmatch(r"(?:.*/)?PIPE_SECTION(?:/(.*))?", rel):
        if m.group(1) is None:
            return f"{entity}.processing[]"
        field = PIPE_SECTION_FIELDS.get(m.group(1))
        return field and f"{entity}.processing[].{field}"
    if m := re.fullmatch(r"(?:DESIGN/)?SPOT_DESCRIPTOR(?:/(.*))?", rel):
        return spot_descriptor(entity, m.group(1))
    if m := re.fullmatch(r"PLATFORM(?:/(.*))?", rel):
        return platform(entity, m.group(1))
    if m := re.fullmatch(r"DATA_BLOCK(?:/(.*))?", rel):
        return data_block(entity, m.group(1))

    if doc == "submission":
        if m := re.fullmatch(r"FILES/FILE/@(\w+)", rel):
            return f"submission.sra.legacy.files[].{m.group(1)}"
        if m := re.fullmatch(r"ACTIONS/ACTION/(\w+)(?:/@(\w+))?", rel):
            attribute = m.group(2)
            if attribute is None:
                return "submission.sra.actions[].type" + NAME_IS_VALUE
            if attribute in ("HoldForPeriod", "notes"):
                return "submission.sra.actions[].legacy." + {"HoldForPeriod": "hold_for_period"}.get(
                    attribute, attribute
                )
            return "submission.sra.actions[]." + {"schema": "object_type", "HoldUntilDate": "hold_until_date"}.get(
                attribute, attribute
            )

    if doc == "experiment":
        if m := re.fullmatch(r"DESIGN/GAP_DESCRIPTOR/GAP/GAP_TYPE/(\w+)(/@orientation)?", rel):
            return "experiments[].legacy.gaps[]." + ("orientation" if m.group(2) else "type" + NAME_IS_VALUE)
        if m := re.fullmatch(r"DESIGN/SAMPLE_DESCRIPTOR/POOL/(MEMBER|DEFAULT_MEMBER)/(.+)", rel):
            member = "members[]" if m.group(1) == "MEMBER" else "default_member"
            field = POOL_MEMBER_FIELDS.get(m.group(2))
            return field and f"experiments[].pool.{member}.{field}"

    if doc == "analysis":
        if m := re.fullmatch(r"ANALYSIS_TYPE/(\w+)(/PROCESSING(/PIPELINE)?)?", rel):
            return "analyses[].analysis_type" + LOWER_NAME_IS_VALUE if m.group(2) is None else CONTAINER
        if m := re.fullmatch(r"TARGETS/IDENTIFIERS(?:/(.*))?", rel):
            return identifiers("relations[derived_from].target", m.group(1) or "")
        if m := re.fullmatch(r"ANALYSIS_TYPE/REFERENCE_ALIGNMENT/SEQ_LABELS/SEQUENCE/@(\w+)", rel):
            return f"analyses[].reference_alignment.seq_labels[].{m.group(1)}"

    if m := re.fullmatch(r"@(\w+)", rel):
        return f"{entity}.{m.group(1)}"

    return None


HEADER = """\
# SRA XML（DRA のメタデータ）の要素と属性を、v3 のどこに置くか。
# 考え方は docs/v3-sra.md、作り方は scripts/sra/README.md。このファイルは
# scripts/sra/build_mapping.py が書くので、手で直さない。
#
# 対象は SRA XSD 1.5d2 から 1.6.1 までの全版に現れる要素と属性に、D-way（drmdb）
# に保存された全版の文書に現れるものを加えたもの。後者には、XSD 1.5 より前の
# 登録にしかない要素も含む。文書の種類ごとに、その根の要素から書く（*_SET は
# 同じ種類を並べる入れ物なので省く）。
#
# 値の読み方:
#   (container)          値を持たない入れ物。子が値を持つ
#   a.b[]                b は list。[] の中の語は注記で、要素の type と、relation なら
#                        target.db（relations[part_of sample] は type が part_of で
#                        target.db が sample の relation）
#   a.properties{key}    dict の key
#   ... (要素名が値)     子要素の名前がその値になる（PLATFORM/ILLUMINA → "ILLUMINA"）
#   ... (要素名を小文字にした値)
#                        同じく、小文字にして値にする（LIBRARY_LAYOUT/PAIRED → "paired"）
#   relations[...]       ルートの relations。source は文書の根の要素
#
# 注記の付いた行は、XSD の一部の版にしかないか、XSD に無いもの。
# 数は D-way の全版の文書のうち、その要素を含むものの数。
"""


def quote(value: str) -> str:
    return yaml.safe_dump(value, allow_unicode=True, width=1000).strip().removesuffix("...").strip()


# --- Checking the rules against the XSDs and the stored documents

SEGMENT = re.compile(r"(\w+)(\[[^\]]*\]|\{[^}]*\})?")

# The kinds of stored value (census_drmdb.rb's kind_of) each v3 type can hold.
READABLE_AS = {int: {"int", "empty"}, float: {"int", "float", "empty"}, bool: {"bool", "empty"}}


def strip_note(location: str) -> str:
    return re.sub(r" \(.*\)$", "", location)


def _unwrap_optional(tp: Any) -> Any:
    if get_origin(tp) in (Union, UnionType):
        args = [a for a in get_args(tp) if a is not NoneType]
        if len(args) != 1:
            raise TypeError(tp)
        return args[0]
    return tp


def resolve(location: str) -> Any:
    """The type at a location such as `experiments[].pool.members[].sample.id`.

    `[...]` is an element of a list and `{...}` a value of a dict; what is inside the brackets is a
    note for the reader. Raises LookupError when the location does not exist in the model.
    """
    tp: Any = DdbjRecord

    for segment in strip_note(location).split("."):
        m = SEGMENT.fullmatch(segment)
        if not m:
            raise LookupError(f"{location}: cannot read {segment!r}")
        name, bracket = m.groups()

        if not (isinstance(tp, type) and issubclass(tp, BaseModel)):
            raise LookupError(f"{location}: {name} is below a non-model")  # noqa: TRY004 -- the location is wrong, not a type
        if name not in tp.model_fields:
            raise LookupError(f"{location}: {tp.__name__} has no field {name!r}")

        # Annotations naming a model defined later (RelationTarget, File) are still strings.
        tp = _unwrap_optional(get_type_hints(tp)[name])
        container = get_origin(tp)

        if bracket is None:
            if container in (list, dict):
                raise LookupError(f"{location}: {name} is a {container.__name__}")
        elif bracket.startswith("["):
            if container is not list:
                raise LookupError(f"{location}: {name} is not a list")
            tp = get_args(tp)[0]
        else:
            if container is not dict:
                raise LookupError(f"{location}: {name} is not a dict")
            tp = get_args(tp)[1]

    return tp


def _segments(location: str) -> list[str]:
    """The location's segments, with the notes inside brackets dropped."""
    return [re.sub(r"\[[^\]]*\]", "[]", segment) for segment in strip_note(location).split(".")] if location else []


def _opens_a_list(doc: str, path: str, location: str) -> bool:
    """Whether location has a list of its own, below where its nearest ancestor with a value goes.

    `runs[].title` for a repeating RUN/TITLE does not: the list is the run's. `relations[]` for
    an *_LINK does, although the run's `runs[]` is not a prefix of it.
    """
    above = ""
    ancestor = path
    while "/" in ancestor:
        ancestor = ancestor.rsplit("/", 1)[0]
        found = rule(doc, ancestor)
        if found not in (None, CONTAINER):
            above = found
            break

    own, theirs = _segments(location), _segments(above)
    common = 0
    while common < min(len(own), len(theirs)) and own[common] == theirs[common]:
        common += 1

    return any(segment.endswith("[]") for segment in own[common:])


def disagreements(doc: str, path: str, location: str, inventory: dict[str, Any], found: dict[str, Any]) -> list[str]:
    """What the XSDs or the stored documents say about path that location contradicts."""
    xsd = inventory[doc].get(path, {})
    stored = found.get(path, {})
    problems = []

    if location == CONTAINER:
        if xsd.get("text") or stored.get("text"):
            problems.append("a container that holds text")
        return problems

    try:
        tp = resolve(location)
    except LookupError as e:
        return [str(e)]

    if (xsd.get("many") or stored.get("max_repeat", 1) > 1) and not _opens_a_list(doc, path, location):
        problems.append("repeats, but goes into no list of its own")

    if tp in READABLE_AS:
        unreadable = set(stored.get("kinds", {})) - READABLE_AS[tp]
        if unreadable:
            problems.append(f"{tp.__name__}, but stored values include {sorted(unreadable)}")

    return problems


def census_paths(census: dict[str, Any], doc: str) -> dict[str, Any]:
    """The census's paths for doc, with a *_SET root dropped (one stored study is wrapped in STUDY_SET)."""
    paths: dict[str, Any] = {}
    for path, entry in census["paths"].get(doc, {}).items():
        head, _, rest = path.partition("/")
        if head.endswith("_SET"):
            if not rest:
                continue
            path = rest  # noqa: PLW2901
        if path in paths:
            entry = {**paths[path], "docs": paths[path]["docs"] + entry["docs"]}  # noqa: PLW2901
        paths[path] = entry
    return paths


def note(doc: str, path: str, inventory: dict[str, Any], found: dict[str, Any], all_versions: list[str]) -> str:
    if path in MALFORMED:
        return f"  # 整形式でない文書を読み直した形。D-way で {found[path]['docs']:,} 文書"
    if path not in inventory[doc]:
        return f"  # XSD に無い。D-way で {found[path]['docs']:,} 文書"
    versions = inventory[doc][path]["versions"]
    if versions != all_versions:
        return "  # XSD " + ", ".join(v.removeprefix("SRA.") for v in versions)
    return ""


def render(inventory: dict[str, Any], census: dict[str, Any]) -> str:
    # The versions in order, as the inventory lists them for a path present in all of them.
    all_versions = max((entry["versions"] for paths in inventory.values() for entry in paths.values()), key=len)
    lines = [HEADER]

    for doc in ENTITIES:
        found = census_paths(census, doc)
        paths = sorted(set(inventory[doc]) | set(found))
        width = max(len(quote(path)) for path in paths) + 1

        lines.append(f"{doc}:")
        for path in paths:
            location = rule(doc, path)
            assert location is not None, path  # noqa: S101 -- main checked
            lines.append(
                f"  {(quote(path) + ':').ljust(width)} {quote(location)}{note(doc, path, inventory, found, all_versions)}"
            )
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("inventory", type=Path)
    parser.add_argument("census", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()

    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    census = json.loads(args.census.read_text(encoding="utf-8"))

    if set(census["documents"]) != set(ENTITIES):
        sys.exit(f"the census has documents of {sorted(census['documents'])}, not of {sorted(ENTITIES)}")

    problems = []
    for doc in ENTITIES:
        found = census_paths(census, doc)
        for path in sorted(set(inventory[doc]) | set(found)):
            location = rule(doc, path)
            if location is None:
                problems.append(f"{doc}: {path}: no rule")
            else:
                problems += [
                    f"{doc}: {path}: {problem}" for problem in disagreements(doc, path, location, inventory, found)
                ]

    if problems:
        print(*problems, sep="\n", file=sys.stderr)
        sys.exit(1)

    args.out.write_text(render(inventory, census), encoding="utf-8")


if __name__ == "__main__":
    main()
