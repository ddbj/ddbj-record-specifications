from tests.unit.insdc.conftest import MakeDataFn

from ddbj_record.insdc.validator import validate_insdc_v1, validate_insdc_v2

# === Phase 2: Qualifier Key Validation (v2) ===


def test_valid_qualifier_key_produces_no_error(make_v2_data: MakeDataFn) -> None:
    data = make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {
                "product": [{"value": "test protein"}],
                "gene": [{"value": "test_gene"}],
            },
        },
    ])
    errors = validate_insdc_v2(data)
    qual_errors = [e for e in errors if e.type == "unknown_qualifier_key"]
    assert qual_errors == []


def test_unknown_qualifier_key_lenient_produces_warning(make_v2_data: MakeDataFn) -> None:
    data = make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {"nonexistent_qual": [{"value": "test"}]},
        },
    ])
    errors = validate_insdc_v2(data, strict=False)
    qual_errors = [e for e in errors if e.type == "unknown_qualifier_key"]
    assert len(qual_errors) == 1
    assert qual_errors[0].severity == "warning"
    assert "nonexistent_qual" in qual_errors[0].msg


def test_unknown_qualifier_key_strict_produces_error(make_v2_data: MakeDataFn) -> None:
    data = make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {"nonexistent_qual": [{"value": "test"}]},
        },
    ])
    errors = validate_insdc_v2(data, strict=True)
    qual_errors = [e for e in errors if e.type == "unknown_qualifier_key"]
    assert len(qual_errors) == 1
    assert qual_errors[0].severity == "error"


def test_missing_mandatory_qualifier_produces_error(make_v2_data: MakeDataFn) -> None:
    data = make_v2_data([
        {
            "type": "assembly_gap",
            "sequence_id": "seq1",
            "qualifiers": {},
        },
    ])
    errors = validate_insdc_v2(data)
    feature_mandatory_errors = [
        e for e in errors
        if e.type == "missing_mandatory_qualifier" and e.severity == "error"
    ]
    assert len(feature_mandatory_errors) == 2
    messages = " ".join(e.msg for e in feature_mandatory_errors)
    assert "estimated_length" in messages
    assert "gap_type" in messages


def test_mandatory_qualifier_present_produces_no_error(make_v2_data: MakeDataFn) -> None:
    data = make_v2_data([
        {
            "type": "assembly_gap",
            "sequence_id": "seq1",
            "qualifiers": {
                "estimated_length": [{"value": "100"}],
                "gap_type": [{"value": "within scaffold"}],
                "linkage_evidence": [{"value": "paired-ends"}],
            },
        },
    ])
    errors = validate_insdc_v2(data)
    feature_mandatory_errors = [
        e for e in errors
        if e.type == "missing_mandatory_qualifier" and e.severity == "error"
    ]
    assert feature_mandatory_errors == []


def test_deprecated_qualifier_produces_warning(make_v2_data: MakeDataFn) -> None:
    data = make_v2_data([
        {
            "type": "CDS",
            "sequence_id": "seq1",
            "qualifiers": {
                "pseudo": [{"value": "true"}],
                "product": [{"value": "test"}],
            },
        },
    ])
    errors = validate_insdc_v2(data)
    deprecated_errors = [e for e in errors if e.type == "deprecated_qualifier"]
    assert len(deprecated_errors) == 1
    assert deprecated_errors[0].severity == "warning"
    assert "pseudogene" in deprecated_errors[0].msg


def test_qualifier_for_wrong_feature_produces_error(make_v2_data: MakeDataFn) -> None:
    data = make_v2_data([
        {
            "type": "centromere",
            "sequence_id": "seq1",
            "qualifiers": {"product": [{"value": "test"}]},
        },
    ])
    errors = validate_insdc_v2(data)
    qual_errors = [e for e in errors if e.type == "unknown_qualifier_key"]
    assert len(qual_errors) >= 1
    assert any("product" in e.msg for e in qual_errors)


# === Phase 2: v2 Source Qualifier Validation ===


def test_v2_source_qualifier_validation_no_false_positive_for_organism_mol_type() -> None:
    data = {
        "sequences": {
            "common_source": {
                "organism": "Test",
                "mol_type": "genomic DNA",
                "qualifiers": {},
            },
            "entries": [],
        },
        "features": [],
    }
    errors = validate_insdc_v2(data)
    mandatory_errors = [e for e in errors if e.type == "missing_mandatory_qualifier"]
    mandatory_msgs = " ".join(e.msg for e in mandatory_errors)
    assert "organism" not in mandatory_msgs
    assert "mol_type" not in mandatory_msgs


def test_v2_source_qualifier_missing_mandatory_is_warning() -> None:
    data = {
        "sequences": {
            "common_source": {
                "organism": "Test",
                "mol_type": "genomic DNA",
                "qualifiers": {},
            },
            "entries": [],
        },
        "features": [],
    }
    errors = validate_insdc_v2(data)
    mandatory_errors = [e for e in errors if e.type == "missing_mandatory_qualifier"]
    for e in mandatory_errors:
        assert e.severity == "warning"


def test_v2_unknown_source_qualifier_produces_warning() -> None:
    data = {
        "sequences": {
            "common_source": {
                "organism": "Test",
                "mol_type": "genomic DNA",
                "qualifiers": {"totally_fake": [{"value": "test"}]},
            },
            "entries": [],
        },
        "features": [],
    }
    errors = validate_insdc_v2(data, strict=False)
    qual_errors = [e for e in errors if e.type == "unknown_qualifier_key"]
    assert len(qual_errors) == 1
    assert "totally_fake" in qual_errors[0].msg


# === Phase 2: v1 Qualifier Validation ===


def test_v1_unknown_qualifier_key_produces_warning(make_v1_data: MakeDataFn) -> None:
    data = make_v1_data([
        {
            "id": "f1",
            "type": "CDS",
            "qualifiers": {"nonexistent_qual": ["test"]},
        },
    ])
    errors = validate_insdc_v1(data, strict=False)
    qual_errors = [e for e in errors if e.type == "unknown_qualifier_key"]
    assert len(qual_errors) >= 1
    assert any("nonexistent_qual" in e.msg for e in qual_errors)


def test_v1_source_feature_mandatory_qualifier_missing_is_warning() -> None:
    data = {
        "ENTRIES": [
            {
                "id": "entry1",
                "features": [
                    {"id": "sf1", "type": "source", "qualifiers": {}},
                ],
            }
        ]
    }
    errors = validate_insdc_v1(data)
    mandatory_errors = [e for e in errors if e.type == "missing_mandatory_qualifier"]
    for e in mandatory_errors:
        assert e.severity == "warning"
