from ddbj_record.insdc.validator import validate_insdc_v2

# === Phase 1: Feature Key Validation ===


def test_known_feature_key_produces_no_error(make_v2_data) -> None:
    data = make_v2_data([
        {"type": "CDS", "sequence_id": "seq1", "qualifiers": {"product": [{"value": "test"}]}},
    ])
    errors = validate_insdc_v2(data)
    feature_errors = [e for e in errors if e.type == "unknown_feature_key"]
    assert feature_errors == []


def test_unknown_feature_key_lenient_produces_warning(make_v2_data) -> None:
    data = make_v2_data([
        {"type": "NONEXISTENT_FEATURE", "sequence_id": "seq1", "qualifiers": {}},
    ])
    errors = validate_insdc_v2(data, strict=False)
    feature_errors = [e for e in errors if e.type == "unknown_feature_key"]
    assert len(feature_errors) == 1
    assert feature_errors[0].severity == "warning"
    assert "NONEXISTENT_FEATURE" in feature_errors[0].msg


def test_unknown_feature_key_strict_produces_error(make_v2_data) -> None:
    data = make_v2_data([
        {"type": "NONEXISTENT_FEATURE", "sequence_id": "seq1", "qualifiers": {}},
    ])
    errors = validate_insdc_v2(data, strict=True)
    feature_errors = [e for e in errors if e.type == "unknown_feature_key"]
    assert len(feature_errors) == 1
    assert feature_errors[0].severity == "error"


def test_unknown_feature_key_loc_includes_index(make_v2_data) -> None:
    data = make_v2_data([
        {"type": "good_type", "sequence_id": "seq1", "qualifiers": {}},
        {"type": "BAD_TYPE", "sequence_id": "seq1", "qualifiers": {}},
    ])
    errors = validate_insdc_v2(data, strict=False)
    feature_errors = [e for e in errors if e.type == "unknown_feature_key"]
    assert len(feature_errors) == 2
    assert feature_errors[1].loc == ["features", 1, "type"]


def test_all_standard_feature_keys_are_valid(make_v2_data) -> None:
    standard_features = [
        "assembly_gap", "C_region", "CDS", "centromere", "D-loop", "D_segment",
        "exon", "gap", "intron", "J_segment", "mat_peptide", "misc_binding",
        "misc_difference", "misc_feature", "misc_RNA", "misc_structure",
        "mobile_element", "modified_base", "mRNA", "ncRNA", "operon", "oriT",
        "precursor_RNA", "primer_bind", "propeptide", "protein_bind",
        "regulatory", "repeat_region", "rep_origin", "rRNA", "sig_peptide",
        "source", "stem_loop", "telomere", "tmRNA", "transit_peptide", "tRNA",
        "unsure", "V_region", "V_segment", "variation", "3'UTR", "5'UTR",
    ]
    for feature_type in standard_features:
        data = make_v2_data([
            {"type": feature_type, "sequence_id": "seq1", "qualifiers": {}},
        ])
        errors = validate_insdc_v2(data)
        feature_errors = [e for e in errors if e.type == "unknown_feature_key"]
        assert feature_errors == [], f"Feature '{feature_type}' should be recognized"


def test_case_sensitive_feature_key(make_v2_data) -> None:
    data = make_v2_data([
        {"type": "cds", "sequence_id": "seq1", "qualifiers": {}},
    ])
    errors = validate_insdc_v2(data)
    feature_errors = [e for e in errors if e.type == "unknown_feature_key"]
    assert len(feature_errors) == 1
    assert "cds" in feature_errors[0].msg
