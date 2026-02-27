"""Tests verifying that error loc paths are accurate for frontend mapping."""

from __future__ import annotations

from tests.unit.insdc.conftest import MakeDataFn

from ddbj_record.insdc.validator import validate_insdc_v1, validate_insdc_v2

# === v2 loc accuracy ===


def test_unknown_feature_key_loc(make_v2_data: MakeDataFn) -> None:
    data = make_v2_data([
        {"type": "FAKE", "sequence_id": "seq1", "qualifiers": {}},
    ])
    errors = validate_insdc_v2(data)
    e = next(e for e in errors if e.type == "unknown_feature_key")
    assert e.loc == ["features", 0, "type"]


def test_unknown_qualifier_key_loc(make_v2_data: MakeDataFn) -> None:
    data = make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {"fake_qual": [{"value": "x"}]},
        },
    ])
    errors = validate_insdc_v2(data)
    e = next(e for e in errors if e.type == "unknown_qualifier_key")
    assert e.loc == ["features", 0, "qualifiers", "fake_qual"]


def test_missing_mandatory_qualifier_loc(make_v2_data: MakeDataFn) -> None:
    data = make_v2_data([
        {
            "type": "assembly_gap",
            "sequence_id": "seq1",
            "qualifiers": {},
        },
    ])
    errors = validate_insdc_v2(data)
    mandatory_errors = [e for e in errors if e.type == "missing_mandatory_qualifier" and e.severity == "error"]
    for e in mandatory_errors:
        assert e.loc[:3] == ["features", 0, "qualifiers"]
        assert len(e.loc) == 4
        assert isinstance(e.loc[3], str)


def test_invalid_cv_value_loc(make_v2_data: MakeDataFn) -> None:
    data = make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {"codon_start": [{"value": "9"}]},
        },
    ])
    errors = validate_insdc_v2(data)
    e = next(e for e in errors if e.type == "invalid_qualifier_value")
    assert e.loc == ["features", 0, "qualifiers", "codon_start", 0, "value"]


def test_deprecated_qualifier_loc(make_v2_data: MakeDataFn) -> None:
    data = make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {"pseudo": [{"value": "true"}]},
        },
    ])
    errors = validate_insdc_v2(data)
    e = next(e for e in errors if e.type == "deprecated_qualifier")
    assert e.loc == ["features", 0, "qualifiers", "pseudo"]


def test_constraint_violation_mutual_exclusion_loc(make_v2_data: MakeDataFn) -> None:
    data = make_v2_data([
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
    e = next(e for e in errors if e.type == "constraint_violation")
    assert e.loc == ["features", 0, "qualifiers"]


def test_constraint_violation_dependency_loc(make_v2_data: MakeDataFn) -> None:
    data = make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {
                "gene_synonym": [{"value": "syn"}],
                "product": [{"value": "protein"}],
            },
        },
    ])
    errors = validate_insdc_v2(data)
    e = next(e for e in errors if e.type == "constraint_violation" and "gene_synonym" in e.msg)
    assert e.loc == ["features", 0, "qualifiers", "gene_synonym"]


def test_common_source_qualifier_loc() -> None:
    data = {
        "sequences": {
            "common_source": {
                "organism": "Test",
                "mol_type": "genomic DNA",
                "qualifiers": {"fake_q": [{"value": "x"}]},
            },
            "entries": [],
        },
        "features": [],
    }
    errors = validate_insdc_v2(data)
    e = next(e for e in errors if e.type == "unknown_qualifier_key")
    assert e.loc == ["sequences", "common_source", "qualifiers", "fake_q"]


def test_source_feature_qualifier_loc() -> None:
    data = {
        "sequences": {
            "common_source": {"organism": "Test", "mol_type": "genomic DNA"},
            "entries": [
                {
                    "id": "seq1",
                    "source_features": [
                        {
                            "id": "sf1",
                            "location": "1..100",
                            "source": {
                                "qualifiers": {"fake_q": [{"value": "x"}]},
                            },
                        }
                    ],
                }
            ],
        },
        "features": [],
    }
    errors = validate_insdc_v2(data)
    e = next(e for e in errors if e.type == "unknown_qualifier_key")
    assert e.loc == [
        "sequences", "entries", 0, "source_features", 0, "source", "qualifiers", "fake_q",
    ]


# === v1 loc accuracy ===


def test_v1_feature_key_loc(make_v1_data: MakeDataFn) -> None:
    data = make_v1_data([
        {"id": "f1", "type": "FAKE", "qualifiers": {}},
    ])
    errors = validate_insdc_v1(data)
    e = next(e for e in errors if e.type == "unknown_feature_key")
    assert e.loc == ["ENTRIES", 0, "features", 1, "type"]


def test_v1_qualifier_key_loc(make_v1_data: MakeDataFn) -> None:
    data = make_v1_data([
        {"id": "f1", "type": "CDS", "qualifiers": {"fake_qual": ["x"]}},
    ])
    errors = validate_insdc_v1(data)
    e = next(e for e in errors if e.type == "unknown_qualifier_key")
    assert e.loc == ["ENTRIES", 0, "features", 1, "qualifiers", "fake_qual"]


def test_v1_invalid_cv_value_loc(make_v1_data: MakeDataFn) -> None:
    data = make_v1_data([
        {"id": "f1", "type": "CDS", "qualifiers": {"codon_start": ["9"]}},
    ])
    errors = validate_insdc_v1(data)
    e = next(e for e in errors if e.type == "invalid_qualifier_value")
    assert e.loc == ["ENTRIES", 0, "features", 1, "qualifiers", "codon_start", 0, "value"]


def test_multiple_features_loc_indexing(make_v2_data: MakeDataFn) -> None:
    data = make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {"product": [{"value": "ok"}]},
        },
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {"codon_start": [{"value": "bad"}]},
        },
    ])
    errors = validate_insdc_v2(data)
    value_errors = [e for e in errors if e.type == "invalid_qualifier_value"]
    assert any(e.loc[1] == 1 for e in value_errors)


# === context field verification ===


def test_invalid_cv_value_context_has_allowed_values(make_v2_data: MakeDataFn) -> None:
    data = make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {"codon_start": [{"value": "9"}]},
        },
    ])
    errors = validate_insdc_v2(data)
    e = next(e for e in errors if e.type == "invalid_qualifier_value")
    assert e.context is not None
    assert "allowed_values" in e.context
    assert isinstance(e.context["allowed_values"], list)
    assert "current_value" in e.context
    assert e.context["current_value"] == "9"


def test_deprecated_qualifier_context_has_replacement(make_v2_data: MakeDataFn) -> None:
    data = make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {"pseudo": [{"value": "true"}]},
        },
    ])
    errors = validate_insdc_v2(data)
    e = next(e for e in errors if e.type == "deprecated_qualifier")
    assert e.context is not None
    assert "replacement" in e.context


def test_constraint_violation_mutual_exclusion_context(make_v2_data: MakeDataFn) -> None:
    data = make_v2_data([
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
    e = next(e for e in errors if e.type == "constraint_violation")
    assert e.context is not None
    assert "conflicting_qualifiers" in e.context
    assert set(e.context["conflicting_qualifiers"]) == {"pseudo", "pseudogene"}


# === stage field verification ===


def test_insdc_errors_have_stage(make_v2_data: MakeDataFn) -> None:
    data = make_v2_data([
        {
            "type": "FAKE",
            "sequence_id": "seq1",
            "qualifiers": {},
        },
    ])
    errors = validate_insdc_v2(data)
    for e in errors:
        assert e.stage == "insdc"
