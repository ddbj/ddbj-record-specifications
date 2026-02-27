"""v1-specific cross-constraint validation tests."""

from __future__ import annotations

from tests.unit.insdc.conftest import MakeDataFn

from ddbj_record.insdc.validator import validate_insdc_v1

# === v1 mutual_exclusion ===


def test_v1_mutual_exclusion_pseudo_pseudogene(make_v1_data: MakeDataFn) -> None:
    data = make_v1_data([
        {
            "id": "f1",
            "type": "CDS",
            "qualifiers": {
                "pseudo": [True],
                "pseudogene": ["processed"],
                "product": ["protein"],
            },
        },
    ])
    errors = validate_insdc_v1(data)
    constraint_errors = [e for e in errors if e.type == "constraint_violation"]
    assert any("pseudo" in e.msg and "pseudogene" in e.msg for e in constraint_errors)


def test_v1_mutual_exclusion_germline_rearranged() -> None:
    data = {
        "ENTRIES": [
            {
                "id": "entry1",
                "features": [
                    {
                        "id": "sf1",
                        "type": "source",
                        "qualifiers": {
                            "organism": ["Test"],
                            "mol_type": ["genomic DNA"],
                            "germline": [True],
                            "rearranged": [True],
                        },
                    },
                ],
            }
        ]
    }
    errors = validate_insdc_v1(data)
    constraint_errors = [e for e in errors if e.type == "constraint_violation"]
    assert any("germline" in e.msg and "rearranged" in e.msg for e in constraint_errors)


def test_v1_no_mutual_exclusion_with_single_qualifier(make_v1_data: MakeDataFn) -> None:
    data = make_v1_data([
        {
            "id": "f1",
            "type": "CDS",
            "qualifiers": {
                "pseudogene": ["processed"],
                "gene": ["test"],
            },
        },
    ])
    errors = validate_insdc_v1(data)
    constraint_errors = [
        e for e in errors
        if e.type == "constraint_violation" and "pseudo" in e.msg and "pseudogene" in e.msg
    ]
    assert constraint_errors == []


# === v1 dependency ===


def test_v1_dependency_metagenome_source_requires_environmental_sample() -> None:
    data = {
        "ENTRIES": [
            {
                "id": "entry1",
                "features": [
                    {
                        "id": "sf1",
                        "type": "source",
                        "qualifiers": {
                            "organism": ["Test"],
                            "mol_type": ["genomic DNA"],
                            "metagenome_source": ["soil metagenome"],
                        },
                    },
                ],
            }
        ]
    }
    errors = validate_insdc_v1(data)
    constraint_errors = [e for e in errors if e.type == "constraint_violation" and "metagenome_source" in e.msg]
    assert len(constraint_errors) >= 1


def test_v1_dependency_metagenome_source_satisfied() -> None:
    data = {
        "ENTRIES": [
            {
                "id": "entry1",
                "features": [
                    {
                        "id": "sf1",
                        "type": "source",
                        "qualifiers": {
                            "organism": ["Test"],
                            "mol_type": ["genomic DNA"],
                            "metagenome_source": ["soil metagenome"],
                            "environmental_sample": [True],
                        },
                    },
                ],
            }
        ]
    }
    errors = validate_insdc_v1(data)
    constraint_errors = [e for e in errors if e.type == "constraint_violation" and "metagenome_source" in e.msg]
    assert constraint_errors == []


# === v1 conditional_mandatory ===


def test_v1_conditional_mandatory_cds_product_required(make_v1_data: MakeDataFn) -> None:
    data = make_v1_data([
        {
            "id": "f1",
            "type": "CDS",
            "qualifiers": {
                "gene": ["test_gene"],
            },
        },
    ])
    errors = validate_insdc_v1(data)
    mandatory_errors = [e for e in errors if e.type == "missing_mandatory_qualifier" and "product" in e.msg]
    assert len(mandatory_errors) >= 1


def test_v1_conditional_mandatory_cds_product_with_pseudo_ok(make_v1_data: MakeDataFn) -> None:
    data = make_v1_data([
        {
            "id": "f1",
            "type": "CDS",
            "qualifiers": {
                "pseudo": [True],
                "gene": ["test_gene"],
            },
        },
    ])
    errors = validate_insdc_v1(data)
    mandatory_errors = [e for e in errors if e.type == "missing_mandatory_qualifier" and "product" in e.msg]
    assert mandatory_errors == []


def test_v1_conditional_mandatory_assembly_gap_linkage_evidence(make_v1_data: MakeDataFn) -> None:
    data = make_v1_data([
        {
            "id": "f1",
            "type": "assembly_gap",
            "qualifiers": {
                "estimated_length": ["100"],
                "gap_type": ["within scaffold"],
            },
        },
    ])
    errors = validate_insdc_v1(data)
    mandatory_errors = [e for e in errors if e.type == "missing_mandatory_qualifier" and "linkage_evidence" in e.msg]
    assert len(mandatory_errors) >= 1


def test_v1_conditional_mandatory_assembly_gap_other_gap_type_ok(make_v1_data: MakeDataFn) -> None:
    data = make_v1_data([
        {
            "id": "f1",
            "type": "assembly_gap",
            "qualifiers": {
                "estimated_length": ["100"],
                "gap_type": ["between scaffolds"],
            },
        },
    ])
    errors = validate_insdc_v1(data)
    mandatory_errors = [e for e in errors if e.type == "missing_mandatory_qualifier" and "linkage_evidence" in e.msg]
    assert mandatory_errors == []
