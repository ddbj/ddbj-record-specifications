import warnings
from typing import Any

import pytest

from ddbj_record.converter.v1_to_v2 import (
    _abbr_candidates_from_fullname,
    _convert_experiments,
    _convert_features,
    _convert_sequences,
    _convert_submission,
    _normalize_abbr,
    _qualifier_value_to_str,
    v1_to_v2,
)
from ddbj_record.schema.v1 import DdbjRecord as DdbjRecordV1
from ddbj_record.schema.v2 import DdbjRecord as DdbjRecordV2

# === fixture-based integration test ===


def test_v1_to_v2_fixture_matches_expected(
    v1_to_v2_input: dict[str, Any],
    v1_to_v2_expected: dict[str, Any],
) -> None:
    v1_obj = DdbjRecordV1.model_validate(v1_to_v2_input)
    result = v1_to_v2(v1_obj)
    result_dict = result.model_dump(exclude_none=True, by_alias=True)
    assert result_dict == v1_to_v2_expected


def test_v1_to_v2_output_schema_version(v1_to_v2_input: dict[str, Any]) -> None:
    v1_obj = DdbjRecordV1.model_validate(v1_to_v2_input)
    result = v1_to_v2(v1_obj)
    assert result.schema_version == "v2.0"


def test_v1_to_v2_output_is_valid_v2(v1_to_v2_input: dict[str, Any]) -> None:
    v1_obj = DdbjRecordV1.model_validate(v1_to_v2_input)
    result = v1_to_v2(v1_obj)
    result_dict = result.model_dump(exclude_none=True, by_alias=True)
    DdbjRecordV2.model_validate(result_dict)


# === _qualifier_value_to_str ===


def test_qualifier_value_to_str_string_passthrough() -> None:
    assert _qualifier_value_to_str("hello") == "hello"


def test_qualifier_value_to_str_true_to_string() -> None:
    assert _qualifier_value_to_str(True) == "true"


def test_qualifier_value_to_str_false_to_string() -> None:
    assert _qualifier_value_to_str(False) == "false"


# === _normalize_abbr ===


def test_normalize_abbr_removes_dots() -> None:
    assert _normalize_abbr("Mishima,H.") == "mishima,h"


def test_normalize_abbr_removes_hyphens() -> None:
    assert _normalize_abbr("Kim-Lee,S.") == "kimlee,s"


def test_normalize_abbr_removes_spaces() -> None:
    assert _normalize_abbr("De La Cruz,J.") == "delacruz,j"


def test_normalize_abbr_lowercases() -> None:
    assert _normalize_abbr("SMITH,J") == "smith,j"


# === _abbr_candidates_from_fullname ===


def test_abbr_candidates_western_name() -> None:
    candidates = _abbr_candidates_from_fullname("Hanako Mishima")
    normalized = {_normalize_abbr(c) for c in candidates}
    assert _normalize_abbr("Mishima,H.") in normalized


def test_abbr_candidates_comma_separated_name() -> None:
    candidates = _abbr_candidates_from_fullname("Mishima, Hanako")
    normalized = {_normalize_abbr(c) for c in candidates}
    assert _normalize_abbr("Mishima,H.") in normalized


def test_abbr_candidates_middle_name() -> None:
    candidates = _abbr_candidates_from_fullname("John Albert Doe")
    normalized = {_normalize_abbr(c) for c in candidates}
    assert _normalize_abbr("Doe,JA.") in normalized or _normalize_abbr("Doe,J.A.") in normalized


def test_abbr_candidates_single_name() -> None:
    candidates = _abbr_candidates_from_fullname("Madonna")
    assert "madonna" in candidates


# === _convert_submission ===


def _make_v1_minimal(overrides: dict[str, Any] | None = None) -> DdbjRecordV1:
    base: dict[str, Any] = {
        "schema_version": "v1.0",
        "COMMON": {
            "SUBMITTER": {
                "ab_name": ["Mishima,H."],
                "contact": "Hanako Mishima",
                "email": "mishima@ddbj.nig.ac.jp",
                "institute": "NIG",
                "country": "Japan",
                "city": "Mishima",
                "street": "Yata 1111",
                "zip": "411-8540",
            },
            "ST_COMMENT": {
                "tagset_id": "Genome-Assembly-Data",
                "Assembly Method": "HGAP v. x.x",
                "Sequencing Technology": "Illumina",
            },
            "trad_submission_category": "GNM",
        },
        "COMMON_SOURCE": {"organism": "Test organism", "mol_type": "genomic DNA"},
        "COMMON_META": {"division": "BCT"},
    }
    if overrides:
        for key, value in overrides.items():
            keys = key.split(".")
            target = base
            for k in keys[:-1]:
                target = target[k]
            target[keys[-1]] = value

    return DdbjRecordV1.model_validate(base)


def test_convert_submission_contact_person_matched() -> None:
    v1_obj = _make_v1_minimal()
    submission = _convert_submission(v1_obj)
    contact = next((s for s in submission.submitters if s.email), None)
    assert contact is not None
    assert contact.name == "Hanako Mishima"
    assert contact.email == "mishima@ddbj.nig.ac.jp"
    assert contact.abbreviation == "Mishima,H."


def test_convert_submission_contact_person_unmatched() -> None:
    v1_obj = _make_v1_minimal({"COMMON.SUBMITTER.contact": "Unknown Person"})
    submission = _convert_submission(v1_obj)
    contact = next((s for s in submission.submitters if s.email), None)
    assert contact is not None
    assert contact.name == "Unknown Person"
    assert contact.abbreviation is None


def test_convert_submission_dblink_to_xrefs() -> None:
    v1_obj = _make_v1_minimal(
        {
            "COMMON.DBLINK": {
                "project": "PRJDB99999",
                "biosample": "SAMD999999",
                "sequence read archive": ["DRR999990"],
            }
        }
    )
    submission = _convert_submission(v1_obj)
    db_names = [x.db for x in submission.db_xrefs]
    assert "bioproject" in db_names
    assert "biosample" in db_names
    assert "insdc.sra" in db_names


def test_convert_submission_reference_status_normalized() -> None:
    v1_obj = _make_v1_minimal(
        {
            "COMMON.REFERENCE": [
                {
                    "title": "Test",
                    "ab_name": ["T,T."],
                    "status": "Unpublished",
                    "year": "2025",
                }
            ]
        }
    )
    submission = _convert_submission(v1_obj)
    assert submission.references[0].status == "unpublished"


def test_convert_submission_reference_status_in_press() -> None:
    v1_obj = _make_v1_minimal(
        {
            "COMMON.REFERENCE": [
                {
                    "title": "Test",
                    "ab_name": ["T,T."],
                    "status": "In Press",
                    "year": "2025",
                }
            ]
        }
    )
    submission = _convert_submission(v1_obj)
    assert submission.references[0].status == "in-press"


def test_convert_submission_hold_date() -> None:
    v1_obj = _make_v1_minimal({"COMMON.DATE": {"hold_date": "20250331"}})
    submission = _convert_submission(v1_obj)
    assert submission.hold_date == "20250331"


def test_convert_submission_consortium() -> None:
    v1_obj = _make_v1_minimal({"COMMON.SUBMITTER.consrtm": "Test Consortium"})
    submission = _convert_submission(v1_obj)
    contact = next((s for s in submission.submitters if s.email), None)
    assert contact is not None
    assert contact.organization is not None
    consortium_orgs = [o for o in contact.organization if o.type == "consortium"]
    assert len(consortium_orgs) == 1
    assert consortium_orgs[0].name == "Test Consortium"


# === _convert_experiments ===


def test_convert_experiments_creates_st_comment_experiment() -> None:
    v1_obj = _make_v1_minimal()
    experiments = _convert_experiments(v1_obj)
    assert len(experiments) == 1
    assert experiments[0].id == "st_comment_experiment"


def test_convert_experiments_platform_type() -> None:
    v1_obj = _make_v1_minimal()
    experiments = _convert_experiments(v1_obj)
    assert experiments[0].platform is not None
    assert experiments[0].platform.platform_type == "Illumina"


def test_convert_experiments_coverage_attribute() -> None:
    v1_obj = _make_v1_minimal(
        {
            "COMMON.ST_COMMENT": {
                "tagset_id": "Genome-Assembly-Data",
                "Assembly Method": "test v. 1",
                "Coverage": "100x",
                "Sequencing Technology": "Illumina",
            }
        }
    )
    experiments = _convert_experiments(v1_obj)
    assert experiments[0].experiment_attributes.get("coverage") == "100x"


def test_convert_experiments_genome_coverage_attribute() -> None:
    v1_obj = _make_v1_minimal(
        {
            "COMMON.ST_COMMENT": {
                "tagset_id": "Genome-Assembly-Data",
                "Assembly Method": "test v. 1",
                "Genome Coverage": "60x",
                "Sequencing Technology": "Illumina",
            }
        }
    )
    experiments = _convert_experiments(v1_obj)
    assert experiments[0].experiment_attributes.get("genome_coverage") == "60x"


# === _convert_sequences ===


def test_convert_sequences_common_source() -> None:
    v1_obj = _make_v1_minimal()
    sequences = _convert_sequences(v1_obj)
    assert sequences.common_source.organism == "Test organism"
    assert sequences.common_source.mol_type == "genomic DNA"


def test_convert_sequences_source_feature_from_entry() -> None:
    v1_obj = _make_v1_minimal(
        {
            "ENTRIES": [
                {
                    "id": "chr1",
                    "name": "chr1",
                    "type": "chromosome",
                    "topology": "circular",
                    "sequence": "atgc",
                    "features": [
                        {
                            "id": "sf1",
                            "type": "source",
                            "location": "1..4",
                            "qualifiers": {
                                "organism": ["Test organism"],
                                "mol_type": ["genomic DNA"],
                                "ff_definition": ["@@[organism]@@ DNA, complete genome"],
                            },
                        }
                    ],
                }
            ]
        }
    )
    sequences = _convert_sequences(v1_obj)
    entry = sequences.entries[0]
    assert len(entry.source_features) == 1
    assert entry.source_features[0].definition == ["@@[organism]@@ DNA, complete genome"]


def test_convert_sequences_ff_definition_to_definition() -> None:
    v1_obj = _make_v1_minimal(
        {
            "ENTRIES": [
                {
                    "id": "chr1",
                    "name": "chr1",
                    "type": "chromosome",
                    "topology": "linear",
                    "sequence": None,
                    "features": [
                        {
                            "id": "sf1",
                            "type": "source",
                            "location": "1..100",
                            "qualifiers": {"ff_definition": ["test definition"]},
                        }
                    ],
                }
            ]
        }
    )
    sequences = _convert_sequences(v1_obj)
    assert sequences.entries[0].source_features[0].definition == ["test definition"]


def test_convert_sequences_comment_feature_to_entry_comments() -> None:
    v1_obj = _make_v1_minimal(
        {
            "ENTRIES": [
                {
                    "id": "chr1",
                    "name": "chr1",
                    "type": "chromosome",
                    "topology": "linear",
                    "sequence": None,
                    "features": [
                        {
                            "id": "sf1",
                            "type": "source",
                            "location": "1..100",
                            "qualifiers": {},
                        },
                        {
                            "id": "c1",
                            "type": "COMMENT",
                            "location": "",
                            "qualifiers": {"line": ["comment line 1", "comment line 2"]},
                        },
                    ],
                }
            ]
        }
    )
    sequences = _convert_sequences(v1_obj)
    assert sequences.entries[0].comments == [["comment line 1", "comment line 2"]]


# === _convert_features ===


def test_convert_features_skips_source() -> None:
    v1_obj = _make_v1_minimal(
        {
            "ENTRIES": [
                {
                    "id": "chr1",
                    "name": "chr1",
                    "type": "chromosome",
                    "topology": "linear",
                    "sequence": None,
                    "features": [
                        {"id": "sf1", "type": "source", "location": "1..100", "qualifiers": {}},
                        {"id": "f1", "type": "CDS", "location": "10..50", "qualifiers": {"product": ["test"]}},
                    ],
                }
            ]
        }
    )
    features = _convert_features(v1_obj)
    assert len(features) == 1
    assert features[0].type == "CDS"


def test_convert_features_sets_sequence_id() -> None:
    v1_obj = _make_v1_minimal(
        {
            "ENTRIES": [
                {
                    "id": "chr1",
                    "name": "chr1",
                    "type": "chromosome",
                    "topology": "linear",
                    "sequence": None,
                    "features": [
                        {"id": "f1", "type": "CDS", "location": "10..50", "qualifiers": {}},
                    ],
                }
            ]
        }
    )
    features = _convert_features(v1_obj)
    assert features[0].sequence_id == "chr1"


def test_convert_features_qualifier_values_converted() -> None:
    v1_obj = _make_v1_minimal(
        {
            "ENTRIES": [
                {
                    "id": "chr1",
                    "name": "chr1",
                    "type": "chromosome",
                    "topology": "linear",
                    "sequence": None,
                    "features": [
                        {
                            "id": "f1",
                            "type": "CDS",
                            "location": "10..50",
                            "qualifiers": {"pseudo": [True], "product": ["test"]},
                        },
                    ],
                }
            ]
        }
    )
    features = _convert_features(v1_obj)
    assert features[0].qualifiers["pseudo"][0].value == "true"
    assert features[0].qualifiers["product"][0].value == "test"


# === BUG-C3: empty string Xref prevention ===


def test_convert_submission_empty_bioproject_skipped() -> None:
    v1_obj = _make_v1_minimal(
        {
            "COMMON.DBLINK": {
                "project": "",
                "biosample": "SAMD999999",
            }
        }
    )
    submission = _convert_submission(v1_obj)
    db_names = [x.db for x in submission.db_xrefs]
    assert "bioproject" not in db_names
    assert "biosample" in db_names


def test_convert_submission_empty_biosample_skipped() -> None:
    v1_obj = _make_v1_minimal(
        {
            "COMMON.DBLINK": {
                "project": "PRJDB99999",
                "biosample": "",
            }
        }
    )
    submission = _convert_submission(v1_obj)
    db_names = [x.db for x in submission.db_xrefs]
    assert "bioproject" in db_names
    assert "biosample" not in db_names


def test_convert_submission_empty_sra_id_skipped() -> None:
    v1_obj = _make_v1_minimal(
        {
            "COMMON.DBLINK": {
                "project": "PRJDB99999",
                "biosample": "SAMD999999",
                "sequence read archive": [""],
            }
        }
    )
    submission = _convert_submission(v1_obj)
    db_names = [x.db for x in submission.db_xrefs]
    assert "insdc.sra" not in db_names


# === BUG-C4: COMMENT features skipped from v2 features[] ===


def test_convert_features_skips_comment_features() -> None:
    v1_obj = _make_v1_minimal(
        {
            "ENTRIES": [
                {
                    "id": "chr1",
                    "name": "chr1",
                    "type": "chromosome",
                    "topology": "linear",
                    "sequence": None,
                    "features": [
                        {"id": "sf1", "type": "source", "location": "1..100", "qualifiers": {}},
                        {"id": "f1", "type": "CDS", "location": "10..50", "qualifiers": {"product": ["test"]}},
                        {"id": "c1", "type": "COMMENT", "location": "", "qualifiers": {"line": ["comment"]}},
                    ],
                }
            ]
        }
    )
    features = _convert_features(v1_obj)
    assert len(features) == 1
    assert features[0].type == "CDS"
    assert all(f.type != "COMMENT" for f in features)


def test_convert_features_locus_tag_id_preserved() -> None:
    v1_obj = _make_v1_minimal(
        {
            "ENTRIES": [
                {
                    "id": "chr1",
                    "name": "chr1",
                    "type": "chromosome",
                    "topology": "linear",
                    "sequence": None,
                    "features": [
                        {
                            "id": "f1",
                            "type": "CDS",
                            "location": "10..50",
                            "qualifiers": {},
                            "locus_tag_id": "00010",
                        },
                    ],
                }
            ]
        }
    )
    features = _convert_features(v1_obj)
    assert features[0].locus_tag_id == "00010"


# === data loss warnings ===


def test_v1_to_v2_contact_unmatched_warns() -> None:
    v1_obj = _make_v1_minimal({"COMMON.SUBMITTER.contact": "Unknown Person"})
    with pytest.warns(UserWarning, match="contact.*did not match"):
        _convert_submission(v1_obj)


# === edge case tests ===


def test_convert_submission_contact_empty_string() -> None:
    v1_obj = _make_v1_minimal({"COMMON.SUBMITTER.contact": ""})
    submission = _convert_submission(v1_obj)
    # Empty contact + ab_name present → email/org assigned to first Person (no ghost)
    assert all(s.abbreviation is not None for s in submission.submitters)
    first = submission.submitters[0]
    assert first.abbreviation == "Mishima,H."
    assert first.email == "mishima@ddbj.nig.ac.jp"
    assert first.organization is not None
    assert len(first.organization) >= 1
    assert first.organization[0].name == "NIG"


def test_convert_submission_contact_empty_ab_name_empty_creates_fallback() -> None:
    v1_obj = _make_v1_minimal({"COMMON.SUBMITTER.contact": "", "COMMON.SUBMITTER.ab_name": []})
    submission = _convert_submission(v1_obj)
    # contact empty + ab_name empty → fallback Person with abbreviation=None
    assert len(submission.submitters) == 1
    assert submission.submitters[0].abbreviation is None
    assert submission.submitters[0].email == "mishima@ddbj.nig.ac.jp"


def test_convert_submission_contact_empty_no_warning() -> None:
    v1_obj = _make_v1_minimal({"COMMON.SUBMITTER.contact": ""})
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _convert_submission(v1_obj)
    contact_warnings = [w for w in caught if "contact" in str(w.message).lower()]
    assert len(contact_warnings) == 0


def test_convert_submission_contact_empty_consortium_to_first() -> None:
    v1_obj = _make_v1_minimal({"COMMON.SUBMITTER.contact": "", "COMMON.SUBMITTER.consrtm": "Test Consortium"})
    submission = _convert_submission(v1_obj)
    first = submission.submitters[0]
    assert first.organization is not None
    consortium_orgs = [o for o in first.organization if o.type == "consortium"]
    assert len(consortium_orgs) == 1
    assert consortium_orgs[0].name == "Test Consortium"


def test_convert_submission_ab_name_empty_list() -> None:
    v1_obj = _make_v1_minimal({"COMMON.SUBMITTER.ab_name": []})
    submission = _convert_submission(v1_obj)
    # With no ab_names, only the fallback Person with abbreviation=None should exist
    assert len(submission.submitters) == 1
    assert submission.submitters[0].abbreviation is None


def test_abbr_candidates_asian_name_pattern() -> None:
    candidates = _abbr_candidates_from_fullname("Yamada Taro")
    normalized = {_normalize_abbr(c) for c in candidates}
    # Asian name: "Yamada" as last name, "Taro" as first name -> "Yamada,T."
    assert _normalize_abbr("Yamada,T.") in normalized


def test_convert_submission_same_surname_candidates() -> None:
    v1_obj = _make_v1_minimal(
        {
            "COMMON.SUBMITTER.ab_name": ["Tanaka,A.", "Tanaka,B."],
            "COMMON.SUBMITTER.contact": "Akiko Tanaka",
        }
    )
    submission = _convert_submission(v1_obj)
    contact = next((s for s in submission.submitters if s.name == "Akiko Tanaka"), None)
    assert contact is not None
    assert contact.abbreviation == "Tanaka,A."


def test_convert_sequences_source_without_mol_type_produces_none_source() -> None:
    v1_obj = _make_v1_minimal(
        {
            "ENTRIES": [
                {
                    "id": "chr1",
                    "name": "chr1",
                    "type": "chromosome",
                    "topology": "linear",
                    "sequence": None,
                    "features": [
                        {
                            "id": "sf1",
                            "type": "source",
                            "location": "1..100",
                            "qualifiers": {"organism": ["Test organism"]},
                        }
                    ],
                }
            ]
        }
    )
    sequences = _convert_sequences(v1_obj)
    # organism without mol_type -> source=None
    assert sequences.entries[0].source_features[0].source is None


# === negative tests ===


def test_v1_to_v2_empty_entries_produces_empty_features() -> None:
    v1_obj = _make_v1_minimal({"ENTRIES": []})
    result = v1_to_v2(v1_obj)
    assert result.features == []
    assert result.sequences.entries == []
