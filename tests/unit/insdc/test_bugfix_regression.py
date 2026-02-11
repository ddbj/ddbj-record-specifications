"""Regression tests for bug fixes 2a-2d."""

from __future__ import annotations

from typing import Any

from ddbj_record.insdc.models import CrossConstraint
from ddbj_record.insdc.validator import (
    _check_single_constraint,
    validate_insdc_v1,
    validate_insdc_v2,
)

# === 2a: exclusion routes to mutual_exclusion (no dead code) ===


def test_exclusion_constraint_type_works_same_as_mutual_exclusion() -> None:
    """The 'exclusion' constraint type should behave identically to 'mutual_exclusion'."""
    constraint = CrossConstraint(
        type="exclusion",
        qualifiers=["qual_a", "qual_b"],
        message="qual_a and qual_b are exclusive",
    )
    qual_keys = {"qual_a", "qual_b"}
    qualifiers: dict[str, Any] = {"qual_a": [{"value": "x"}], "qual_b": [{"value": "y"}]}
    loc_prefix: list[str | int] = ["features", 0]

    errors = _check_single_constraint(constraint, qual_keys, qualifiers, "CDS", loc_prefix)
    assert len(errors) == 1
    assert errors[0].type == "constraint_violation"


def test_exclusion_no_violation_with_one_qualifier() -> None:
    constraint = CrossConstraint(
        type="exclusion",
        qualifiers=["qual_a", "qual_b"],
        message="qual_a and qual_b are exclusive",
    )
    qual_keys = {"qual_a"}
    qualifiers: dict[str, Any] = {"qual_a": [{"value": "x"}]}
    loc_prefix: list[str | int] = ["features", 0]

    errors = _check_single_constraint(constraint, qual_keys, qualifiers, "CDS", loc_prefix)
    assert errors == []


# === 2b: gene_synonym dependency with OR requires ===


def test_gene_synonym_with_gene_produces_no_error(make_v2_data) -> None:
    data = make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {
                "gene": [{"value": "geneA"}],
                "gene_synonym": [{"value": "synA"}],
                "product": [{"value": "proteinA"}],
            },
        },
    ])
    errors = validate_insdc_v2(data)
    constraint_errors = [e for e in errors if e.type == "constraint_violation" and "gene_synonym" in e.msg]
    assert constraint_errors == []


def test_gene_synonym_with_locus_tag_produces_no_error(make_v2_data) -> None:
    data = make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {
                "locus_tag": [{"value": "TAG_001"}],
                "gene_synonym": [{"value": "synA"}],
                "product": [{"value": "proteinA"}],
            },
        },
    ])
    errors = validate_insdc_v2(data)
    constraint_errors = [e for e in errors if e.type == "constraint_violation" and "gene_synonym" in e.msg]
    assert constraint_errors == []


def test_gene_synonym_without_gene_or_locus_tag_produces_error(make_v2_data) -> None:
    data = make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {
                "gene_synonym": [{"value": "synA"}],
                "product": [{"value": "proteinA"}],
            },
        },
    ])
    errors = validate_insdc_v2(data)
    constraint_errors = [e for e in errors if e.type == "constraint_violation" and "gene_synonym" in e.msg]
    assert len(constraint_errors) == 1


def test_v1_gene_synonym_with_locus_tag_produces_no_error(make_v1_data) -> None:
    data = make_v1_data([
        {
            "id": "f1",
            "type": "CDS",
            "qualifiers": {
                "locus_tag": ["TAG_001"],
                "gene_synonym": ["synA"],
                "product": ["proteinA"],
            },
        },
    ])
    errors = validate_insdc_v1(data)
    constraint_errors = [e for e in errors if e.type == "constraint_violation" and "gene_synonym" in e.msg]
    assert constraint_errors == []


def test_v1_gene_synonym_without_gene_or_locus_tag_produces_error(make_v1_data) -> None:
    data = make_v1_data([
        {
            "id": "f1",
            "type": "CDS",
            "qualifiers": {
                "gene_synonym": ["synA"],
                "product": ["proteinA"],
            },
        },
    ])
    errors = validate_insdc_v1(data)
    constraint_errors = [e for e in errors if e.type == "constraint_violation" and "gene_synonym" in e.msg]
    assert len(constraint_errors) == 1


# === 2c: Non-allowed qualifier value validation skip ===


def test_non_allowed_qualifier_not_value_validated(make_v2_data) -> None:
    """A qualifier not in the feature's allowed list should not get value-validated."""
    data = make_v2_data([
        {
            "type": "centromere",
            "sequence_id": "seq1",
            "qualifiers": {
                "codon_start": [{"value": "999"}],  # invalid CV, but not allowed on centromere
            },
        },
    ])
    errors = validate_insdc_v2(data)
    # Should get unknown_qualifier_key but NOT invalid_qualifier_value
    unknown_errors = [e for e in errors if e.type == "unknown_qualifier_key"]
    value_errors = [e for e in errors if e.type == "invalid_qualifier_value"]
    assert len(unknown_errors) >= 1
    assert value_errors == []


def test_allowed_qualifier_still_value_validated(make_v2_data) -> None:
    """A qualifier in the feature's allowed list should still be value-validated."""
    data = make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {
                "codon_start": [{"value": "999"}],
            },
        },
    ])
    errors = validate_insdc_v2(data)
    value_errors = [e for e in errors if e.type == "invalid_qualifier_value" and "codon_start" in e.msg]
    assert len(value_errors) >= 1


def test_v1_non_allowed_qualifier_not_value_validated(make_v1_data) -> None:
    data = make_v1_data([
        {
            "id": "f1",
            "type": "centromere",
            "qualifiers": {
                "codon_start": ["999"],
            },
        },
    ])
    errors = validate_insdc_v1(data)
    unknown_errors = [e for e in errors if e.type == "unknown_qualifier_key"]
    value_errors = [e for e in errors if e.type == "invalid_qualifier_value"]
    assert len(unknown_errors) >= 1
    assert value_errors == []


# === 2d: Merged qualifier cross-constraint for source_features ===


def test_cross_constraint_detects_conflict_across_common_and_source_feature() -> None:
    """germline in common_source + rearranged in source_feature should trigger mutual_exclusion."""
    data = {
        "sequences": {
            "common_source": {
                "organism": "Test",
                "mol_type": "genomic DNA",
                "qualifiers": {
                    "germline": [{"value": "true"}],
                },
            },
            "entries": [
                {
                    "id": "seq1",
                    "source_features": [
                        {
                            "id": "sf1",
                            "location": "1..100",
                            "source": {
                                "qualifiers": {
                                    "rearranged": [{"value": "true"}],
                                },
                            },
                        }
                    ],
                }
            ],
        },
        "features": [],
    }
    errors = validate_insdc_v2(data)
    constraint_errors = [e for e in errors if e.type == "constraint_violation"]
    assert any("germline" in e.msg and "rearranged" in e.msg for e in constraint_errors)


def test_no_cross_constraint_conflict_when_common_and_source_feature_compatible() -> None:
    data = {
        "sequences": {
            "common_source": {
                "organism": "Test",
                "mol_type": "genomic DNA",
                "qualifiers": {
                    "germline": [{"value": "true"}],
                },
            },
            "entries": [
                {
                    "id": "seq1",
                    "source_features": [
                        {
                            "id": "sf1",
                            "location": "1..100",
                            "source": {
                                "qualifiers": {
                                    "note": [{"value": "some note"}],
                                },
                            },
                        }
                    ],
                }
            ],
        },
        "features": [],
    }
    errors = validate_insdc_v2(data)
    constraint_errors = [
        e for e in errors
        if e.type == "constraint_violation" and "germline" in e.msg and "rearranged" in e.msg
    ]
    assert constraint_errors == []


def test_dependency_satisfied_across_common_and_source_feature() -> None:
    """metagenome_source in source_feature + environmental_sample in common_source should pass."""
    data = {
        "sequences": {
            "common_source": {
                "organism": "Test",
                "mol_type": "genomic DNA",
                "qualifiers": {
                    "environmental_sample": [{"value": "true"}],
                },
            },
            "entries": [
                {
                    "id": "seq1",
                    "source_features": [
                        {
                            "id": "sf1",
                            "location": "1..100",
                            "source": {
                                "qualifiers": {
                                    "metagenome_source": [{"value": "soil metagenome"}],
                                },
                            },
                        }
                    ],
                }
            ],
        },
        "features": [],
    }
    errors = validate_insdc_v2(data)
    constraint_errors = [
        e for e in errors
        if e.type == "constraint_violation" and "metagenome_source" in e.msg
    ]
    assert constraint_errors == []
