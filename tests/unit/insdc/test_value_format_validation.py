from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from ddbj_record.insdc import load_insdc_definition
from ddbj_record.insdc.validator import validate_insdc_v1, validate_insdc_v2

from .conftest import _make_v2_data_raw


def _make_v2_data(features: list[dict[str, Any]]) -> dict[str, Any]:
    """Standalone helper for Hypothesis tests (cannot use pytest fixtures)."""
    return _make_v2_data_raw(features)


# === Phase 3: Controlled Vocabulary Validation ===


def test_valid_controlled_vocabulary_value_produces_no_error() -> None:
    data = _make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {
                "codon_start": [{"value": "1"}],
                "transl_table": [{"value": "11"}],
            },
        },
    ])
    errors = validate_insdc_v2(data)
    value_errors = [e for e in errors if e.type == "invalid_qualifier_value"]
    assert value_errors == []


def test_invalid_controlled_vocabulary_value_produces_error() -> None:
    data = _make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {
                "codon_start": [{"value": "4"}],
            },
        },
    ])
    errors = validate_insdc_v2(data)
    value_errors = [e for e in errors if e.type == "invalid_qualifier_value"]
    assert len(value_errors) == 1
    assert "codon_start" in value_errors[0].msg
    assert value_errors[0].severity == "error"


def test_invalid_mol_type_produces_error() -> None:
    data = {
        "sequences": {
            "common_source": {
                "organism": "Test",
                "mol_type": "genomic DNA",
                "qualifiers": {"mol_type": [{"value": "invalid_type"}]},
            },
            "entries": [],
        },
        "features": [],
    }
    errors = validate_insdc_v2(data)
    value_errors = [e for e in errors if e.type == "invalid_qualifier_value"]
    assert any("mol_type" in e.msg for e in value_errors)


@pytest.mark.parametrize("value", ["1", "2", "3"])
def test_valid_codon_start_values(value: str) -> None:
    data = _make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {"codon_start": [{"value": value}]},
        },
    ])
    errors = validate_insdc_v2(data)
    value_errors = [e for e in errors if e.type == "invalid_qualifier_value"]
    assert value_errors == []


@pytest.mark.parametrize("value", ["0", "4", "-1", "abc", ""])
def test_invalid_codon_start_values(value: str) -> None:
    data = _make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {"codon_start": [{"value": value}]},
        },
    ])
    errors = validate_insdc_v2(data)
    value_errors = [e for e in errors if e.type == "invalid_qualifier_value"]
    assert len(value_errors) >= 1


# === Phase 3: Boolean (none format) Validation ===


def test_boolean_qualifier_with_true_value_is_valid() -> None:
    data = _make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {
                "pseudo": [{"value": "true"}],
            },
        },
    ])
    errors = validate_insdc_v2(data)
    value_errors = [e for e in errors if e.type == "invalid_qualifier_value"]
    assert value_errors == []


def test_boolean_qualifier_with_false_value_is_invalid() -> None:
    data = _make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {
                "pseudo": [{"value": "false"}],
            },
        },
    ])
    errors = validate_insdc_v2(data)
    value_errors = [e for e in errors if e.type == "invalid_qualifier_value"]
    assert len(value_errors) == 1
    assert "pseudo" in value_errors[0].msg


def test_boolean_qualifier_with_yes_value_is_invalid() -> None:
    data = _make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {
                "pseudo": [{"value": "yes"}],
            },
        },
    ])
    errors = validate_insdc_v2(data)
    value_errors = [e for e in errors if e.type == "invalid_qualifier_value"]
    assert len(value_errors) >= 1


# === Phase 3: Cross-Constraint Validation ===


def test_mutual_exclusion_germline_rearranged() -> None:
    data = {
        "sequences": {
            "common_source": {
                "organism": "Test",
                "mol_type": "genomic DNA",
                "qualifiers": {
                    "germline": [{"value": "true"}],
                    "rearranged": [{"value": "true"}],
                },
            },
            "entries": [],
        },
        "features": [],
    }
    errors = validate_insdc_v2(data)
    constraint_errors = [e for e in errors if e.type == "constraint_violation"]
    assert len(constraint_errors) >= 1
    assert any("germline" in e.msg and "rearranged" in e.msg for e in constraint_errors)


def test_mutual_exclusion_pseudo_pseudogene() -> None:
    data = _make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {
                "pseudo": [{"value": "true"}],
                "pseudogene": [{"value": "processed"}],
            },
        },
    ])
    errors = validate_insdc_v2(data)
    constraint_errors = [e for e in errors if e.type == "constraint_violation"]
    assert len(constraint_errors) >= 1
    assert any("pseudo" in e.msg and "pseudogene" in e.msg for e in constraint_errors)


def test_no_mutual_exclusion_when_only_one_present() -> None:
    data = _make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {
                "pseudogene": [{"value": "processed"}],
            },
        },
    ])
    errors = validate_insdc_v2(data)
    constraint_errors = [e for e in errors if e.type == "constraint_violation"]
    assert constraint_errors == []


def test_conditional_mandatory_cds_product_without_pseudo() -> None:
    data = _make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {
                "gene": [{"value": "test_gene"}],
            },
        },
    ])
    errors = validate_insdc_v2(data)
    mandatory_errors = [e for e in errors if e.type == "missing_mandatory_qualifier"]
    assert any("product" in e.msg for e in mandatory_errors)


def test_conditional_mandatory_cds_product_with_pseudo_no_error() -> None:
    data = _make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {
                "pseudo": [{"value": "true"}],
                "gene": [{"value": "test_gene"}],
            },
        },
    ])
    errors = validate_insdc_v2(data)
    mandatory_errors = [e for e in errors if e.type == "missing_mandatory_qualifier" and "product" in e.msg]
    assert mandatory_errors == []


def test_conditional_mandatory_cds_product_with_pseudogene_no_error() -> None:
    data = _make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {
                "pseudogene": [{"value": "unprocessed"}],
                "gene": [{"value": "test_gene"}],
            },
        },
    ])
    errors = validate_insdc_v2(data)
    mandatory_errors = [e for e in errors if e.type == "missing_mandatory_qualifier" and "product" in e.msg]
    assert mandatory_errors == []


def test_conditional_mandatory_assembly_gap_linkage_evidence() -> None:
    data = _make_v2_data([
        {
            "type": "assembly_gap",
            "sequence_id": "seq1",
            "qualifiers": {
                "estimated_length": [{"value": "100"}],
                "gap_type": [{"value": "within scaffold"}],
            },
        },
    ])
    errors = validate_insdc_v2(data)
    mandatory_errors = [e for e in errors if e.type == "missing_mandatory_qualifier" and "linkage_evidence" in e.msg]
    assert len(mandatory_errors) >= 1


def test_conditional_mandatory_assembly_gap_linkage_evidence_not_required_for_other_gap_types() -> None:
    data = _make_v2_data([
        {
            "type": "assembly_gap",
            "sequence_id": "seq1",
            "qualifiers": {
                "estimated_length": [{"value": "100"}],
                "gap_type": [{"value": "between scaffolds"}],
            },
        },
    ])
    errors = validate_insdc_v2(data)
    mandatory_errors = [e for e in errors if e.type == "missing_mandatory_qualifier" and "linkage_evidence" in e.msg]
    assert mandatory_errors == []


def test_dependency_metagenome_source_requires_environmental_sample() -> None:
    data = {
        "sequences": {
            "common_source": {
                "organism": "Test",
                "mol_type": "genomic DNA",
                "qualifiers": {
                    "metagenome_source": [{"value": "soil metagenome"}],
                },
            },
            "entries": [],
        },
        "features": [],
    }
    errors = validate_insdc_v2(data)
    constraint_errors = [e for e in errors if e.type == "constraint_violation"]
    assert any("metagenome_source" in e.msg for e in constraint_errors)


def test_dependency_metagenome_source_with_environmental_sample_ok() -> None:
    data = {
        "sequences": {
            "common_source": {
                "organism": "Test",
                "mol_type": "genomic DNA",
                "qualifiers": {
                    "metagenome_source": [{"value": "soil metagenome"}],
                    "environmental_sample": [{"value": "true"}],
                },
            },
            "entries": [],
        },
        "features": [],
    }
    errors = validate_insdc_v2(data)
    constraint_errors = [e for e in errors if e.type == "constraint_violation" and "metagenome_source" in e.msg]
    assert constraint_errors == []


# === v1 Value Format Validation ===


def test_v1_controlled_vocabulary_validation() -> None:
    data = {
        "ENTRIES": [
            {
                "id": "entry1",
                "features": [
                    {"id": "sf1", "type": "source", "qualifiers": {
                        "organism": ["Test"], "mol_type": ["invalid_type"],
                    }},
                ],
            }
        ]
    }
    errors = validate_insdc_v1(data)
    value_errors = [e for e in errors if e.type == "invalid_qualifier_value"]
    assert any("mol_type" in e.msg for e in value_errors)


def test_v1_boolean_qualifier_with_bool_true_is_valid() -> None:
    data = {
        "ENTRIES": [
            {
                "id": "entry1",
                "features": [
                    {"id": "sf1", "type": "source", "qualifiers": {
                        "organism": ["Test"], "mol_type": ["genomic DNA"],
                    }},
                    {"id": "f1", "type": "CDS", "qualifiers": {
                        "pseudo": [True],
                    }},
                ],
            }
        ]
    }
    errors = validate_insdc_v1(data)
    value_errors = [e for e in errors if e.type == "invalid_qualifier_value" and "pseudo" in e.msg]
    assert value_errors == []


# === Hypothesis PBT: controlled vocabulary ===


@given(value=st.text(min_size=1, max_size=50))
@settings(max_examples=50)
def test_pbt_random_codon_start_value_is_validated(value: str) -> None:
    data = _make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {"codon_start": [{"value": value}]},
        },
    ])
    errors = validate_insdc_v2(data)
    value_errors = [e for e in errors if e.type == "invalid_qualifier_value" and "codon_start" in e.msg]

    if value in ("1", "2", "3"):
        assert value_errors == []
    else:
        assert len(value_errors) >= 1


@given(value=st.text(min_size=1, max_size=50))
@settings(max_examples=50)
def test_pbt_random_pseudogene_value_is_validated(value: str) -> None:
    definition = load_insdc_definition()
    valid_values = definition.qualifiers["pseudogene"].controlled_vocabulary or []

    data = _make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {"pseudogene": [{"value": value}]},
        },
    ])
    errors = validate_insdc_v2(data)
    value_errors = [e for e in errors if e.type == "invalid_qualifier_value" and "pseudogene" in e.msg]

    if value in valid_values:
        assert value_errors == []
    else:
        assert len(value_errors) >= 1
