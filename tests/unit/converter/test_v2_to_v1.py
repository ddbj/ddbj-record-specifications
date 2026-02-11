from typing import Any

import pytest

from ddbj_record.converter.v1_to_v2 import v1_to_v2
from ddbj_record.converter.v2_to_v1 import (
    _convert_common,
    _convert_common_meta,
    _convert_common_source,
    _convert_entries,
    _qualifier_value_to_union,
    v2_to_v1,
)
from ddbj_record.schema.v1 import DdbjRecord as DdbjRecordV1
from ddbj_record.schema.v2 import DdbjRecord as DdbjRecordV2

# === fixture-based integration test ===


def test_v2_to_v1_fixture_matches_expected(
    v2_to_v1_input: dict[str, Any],
    v2_to_v1_expected: dict[str, Any],
) -> None:
    v2_obj = DdbjRecordV2.model_validate(v2_to_v1_input)
    result = v2_to_v1(v2_obj)
    result_dict = result.model_dump(exclude_none=True, by_alias=True)
    assert result_dict == v2_to_v1_expected


def test_v2_to_v1_output_schema_version(v2_to_v1_input: dict[str, Any]) -> None:
    v2_obj = DdbjRecordV2.model_validate(v2_to_v1_input)
    result = v2_to_v1(v2_obj)
    assert result.schema_version == "v1.0"


def test_v2_to_v1_output_is_valid_v1(v2_to_v1_input: dict[str, Any]) -> None:
    v2_obj = DdbjRecordV2.model_validate(v2_to_v1_input)
    result = v2_to_v1(v2_obj)
    result_dict = result.model_dump(exclude_none=True, by_alias=True)
    DdbjRecordV1.model_validate(result_dict)


# === _qualifier_value_to_union ===


def test_qualifier_value_to_union_true_string_returns_bool() -> None:
    assert _qualifier_value_to_union("true") is True


def test_qualifier_value_to_union_false_string_returns_bool() -> None:
    assert _qualifier_value_to_union("false") is False


def test_qualifier_value_to_union_regular_string_passthrough() -> None:
    assert _qualifier_value_to_union("hello") == "hello"


def test_qualifier_value_to_union_numeric_string_passthrough() -> None:
    assert _qualifier_value_to_union("11") == "11"


# === helper to build minimal v2 data ===


def _make_v2_minimal(overrides: dict[str, Any] | None = None) -> DdbjRecordV2:
    base: dict[str, Any] = {
        "schema_version": "v2.0",
        "provenance": {},
        "submission": {
            "submitters": [
                {
                    "name": "Test User",
                    "abbreviation": "User,T.",
                    "email": "test@example.com",
                    "organization": [
                        {
                            "name": "Test Institute",
                            "type": "institution",
                            "address": {
                                "country": "Japan",
                                "city": "Tokyo",
                            },
                        }
                    ],
                }
            ],
            "references": [
                {
                    "title": "Test Title",
                    "authors": [{"abbreviation": "User,T."}],
                    "status": "unpublished",
                    "year": "2025",
                }
            ],
        },
        "experiments": [
            {
                "id": "st_comment_experiment",
                "platform": {"platform_type": "Illumina"},
                "experiment_attributes": {
                    "tagset_id": "Genome-Assembly-Data",
                    "assembly_method": "test v. 1",
                },
            }
        ],
        "sequences": {
            "common_source": {"organism": "Test organism", "mol_type": "genomic DNA"},
        },
    }
    if overrides:
        _deep_merge(base, overrides)

    return DdbjRecordV2.model_validate(base)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


# === _convert_common ===


def test_convert_common_dblink_from_xrefs() -> None:
    v2_obj = _make_v2_minimal(
        {
            "submission": {
                "submitters": [
                    {
                        "name": "Test",
                        "abbreviation": "T,T.",
                        "email": "t@t.com",
                        "organization": [
                            {"name": "Inst", "type": "institution", "address": {"country": "JP", "city": "T"}}
                        ],
                    }
                ],
                "db_xrefs": [
                    {"db": "bioproject", "id": "PRJDB99999"},
                    {"db": "biosample", "id": "SAMD999999"},
                    {"db": "insdc.sra", "id": "DRR999990"},
                ],
                "references": [{"title": "T", "authors": [], "status": "unpublished", "year": "2025"}],
            }
        }
    )
    common = _convert_common(v2_obj)
    assert common.DBLINK is not None
    assert common.DBLINK.project == "PRJDB99999"
    assert common.DBLINK.biosample == "SAMD999999"
    assert common.DBLINK.sequence_read_archive == ["DRR999990"]


def test_convert_common_submitter_fields() -> None:
    v2_obj = _make_v2_minimal()
    common = _convert_common(v2_obj)
    assert common.SUBMITTER.contact == "Test User"
    assert common.SUBMITTER.email == "test@example.com"
    assert common.SUBMITTER.institute == "Test Institute"


def test_convert_common_reference_status_denormalized() -> None:
    v2_obj = _make_v2_minimal()
    common = _convert_common(v2_obj)
    assert common.REFERENCE[0].status == "Unpublished"


def test_convert_common_reference_status_in_press_denormalized() -> None:
    v2_obj = _make_v2_minimal(
        {
            "submission": {
                "submitters": [
                    {
                        "name": "T",
                        "abbreviation": "T,T.",
                        "email": "t@t.com",
                        "organization": [
                            {"name": "I", "type": "institution", "address": {"country": "JP", "city": "T"}}
                        ],
                    }
                ],
                "references": [
                    {"title": "T", "authors": [{"abbreviation": "T,T."}], "status": "in-press", "year": "2025"}
                ],
            }
        }
    )
    common = _convert_common(v2_obj)
    assert common.REFERENCE[0].status == "In Press"


def test_convert_common_st_comment_from_experiment() -> None:
    v2_obj = _make_v2_minimal()
    common = _convert_common(v2_obj)
    assert common.ST_COMMENT.sequencing_technology == "Illumina"
    assert common.ST_COMMENT.tagset_id == "Genome-Assembly-Data"


def test_convert_common_date_from_hold_date() -> None:
    v2_obj = _make_v2_minimal(
        {
            "submission": {
                "submitters": [
                    {
                        "name": "T",
                        "abbreviation": "T,T.",
                        "email": "t@t.com",
                        "organization": [
                            {"name": "I", "type": "institution", "address": {"country": "JP", "city": "T"}}
                        ],
                    }
                ],
                "references": [{"title": "T", "authors": [], "status": "unpublished", "year": "2025"}],
                "hold_date": "2025-03-31",
            }
        }
    )
    common = _convert_common(v2_obj)
    assert common.DATE is not None
    assert common.DATE.hold_date == "2025-03-31"


def test_convert_common_trad_submission_category() -> None:
    v2_obj = _make_v2_minimal(
        {
            "submission": {
                "submitters": [
                    {
                        "name": "T",
                        "abbreviation": "T,T.",
                        "email": "t@t.com",
                        "organization": [
                            {"name": "I", "type": "institution", "address": {"country": "JP", "city": "T"}}
                        ],
                    }
                ],
                "references": [{"title": "T", "authors": [], "status": "unpublished", "year": "2025"}],
                "trad_submission_category": "WGS",
            }
        }
    )
    common = _convert_common(v2_obj)
    assert common.trad_submission_category == "WGS"


def test_convert_common_trad_submission_category_defaults_to_gnm() -> None:
    v2_obj = _make_v2_minimal()
    common = _convert_common(v2_obj)
    assert common.trad_submission_category == "GNM"


def test_convert_common_comments() -> None:
    v2_obj = _make_v2_minimal(
        {
            "submission": {
                "submitters": [
                    {
                        "name": "T",
                        "abbreviation": "T,T.",
                        "email": "t@t.com",
                        "organization": [
                            {"name": "I", "type": "institution", "address": {"country": "JP", "city": "T"}}
                        ],
                    }
                ],
                "references": [{"title": "T", "authors": [], "status": "unpublished", "year": "2025"}],
                "comments": [["line1", "line2"], ["line3"]],
            }
        }
    )
    common = _convert_common(v2_obj)
    assert len(common.COMMENT) == 2
    assert common.COMMENT[0].line == ["line1", "line2"]


# === _pick_contact_person (tested via _convert_common) ===


def test_pick_contact_person_prefers_name_and_email() -> None:
    v2_obj = _make_v2_minimal(
        {
            "submission": {
                "submitters": [
                    {"abbreviation": "A,A."},
                    {
                        "name": "Best Contact",
                        "abbreviation": "B,B.",
                        "email": "best@example.com",
                        "organization": [
                            {"name": "I", "type": "institution", "address": {"country": "JP", "city": "T"}}
                        ],
                    },
                ],
                "references": [{"title": "T", "authors": [], "status": "unpublished", "year": "2025"}],
            }
        }
    )
    common = _convert_common(v2_obj)
    assert common.SUBMITTER.contact == "Best Contact"


def test_pick_contact_person_fallback_to_email() -> None:
    v2_obj = _make_v2_minimal(
        {
            "submission": {
                "submitters": [
                    {"abbreviation": "A,A."},
                    {
                        "abbreviation": "B,B.",
                        "email": "b@example.com",
                        "organization": [
                            {"name": "I", "type": "institution", "address": {"country": "JP", "city": "T"}}
                        ],
                    },
                ],
                "references": [{"title": "T", "authors": [], "status": "unpublished", "year": "2025"}],
            }
        }
    )
    common = _convert_common(v2_obj)
    assert common.SUBMITTER.email == "b@example.com"


def test_pick_contact_person_fallback_to_org() -> None:
    v2_obj = _make_v2_minimal(
        {
            "submission": {
                "submitters": [
                    {"abbreviation": "A,A."},
                    {
                        "abbreviation": "B,B.",
                        "organization": [
                            {"name": "OrgInst", "type": "institution", "address": {"country": "JP", "city": "T"}}
                        ],
                    },
                ],
                "references": [{"title": "T", "authors": [], "status": "unpublished", "year": "2025"}],
            }
        }
    )
    common = _convert_common(v2_obj)
    assert common.SUBMITTER.institute == "OrgInst"


def test_pick_contact_person_fallback_to_first() -> None:
    v2_obj = _make_v2_minimal(
        {
            "submission": {
                "submitters": [
                    {"abbreviation": "First,F."},
                    {"abbreviation": "Second,S."},
                ],
                "references": [{"title": "T", "authors": [], "status": "unpublished", "year": "2025"}],
            }
        }
    )
    common = _convert_common(v2_obj)
    assert "First,F." in common.SUBMITTER.ab_name


# === _convert_common_source ===


def test_convert_common_source_basic() -> None:
    v2_obj = _make_v2_minimal()
    cs = _convert_common_source(v2_obj)
    assert cs.organism == "Test organism"
    assert cs.mol_type == "genomic DNA"


def test_convert_common_source_single_qualifier() -> None:
    v2_obj = _make_v2_minimal(
        {
            "sequences": {
                "common_source": {
                    "organism": "Test",
                    "mol_type": "genomic DNA",
                    "qualifiers": {"strain": [{"value": "LOOC260"}]},
                }
            }
        }
    )
    cs = _convert_common_source(v2_obj)
    assert cs.model_extra is not None
    assert cs.model_extra["strain"] == "LOOC260"


def test_convert_common_source_multiple_qualifiers() -> None:
    v2_obj = _make_v2_minimal(
        {
            "sequences": {
                "common_source": {
                    "organism": "Test",
                    "mol_type": "genomic DNA",
                    "qualifiers": {"note": [{"value": "note1"}, {"value": "note2"}]},
                }
            }
        }
    )
    cs = _convert_common_source(v2_obj)
    assert cs.model_extra is not None
    assert cs.model_extra["note"] == ["note1", "note2"]


# === _convert_common_meta ===


def test_convert_common_meta_division_default() -> None:
    v2_obj = _make_v2_minimal()
    meta = _convert_common_meta(v2_obj)
    assert meta.division == "BCT"


def test_convert_common_meta_dfast_version() -> None:
    v2_obj = _make_v2_minimal({"provenance": {"dfast_version": "1.3.4"}})
    meta = _convert_common_meta(v2_obj)
    assert meta.dfast_version == "1.3.4"


# === _convert_entries ===


def test_convert_entries_source_feature_rebuilt() -> None:
    v2_obj = _make_v2_minimal(
        {
            "sequences": {
                "common_source": {"organism": "Test", "mol_type": "genomic DNA"},
                "entries": [
                    {
                        "id": "chr1",
                        "name": "chr1",
                        "type": "chromosome",
                        "topology": "linear",
                        "source_features": [
                            {
                                "id": "sf1",
                                "location": "1..100",
                                "source": {
                                    "organism": "Test",
                                    "mol_type": "genomic DNA",
                                    "qualifiers": {"strain": [{"value": "S1"}]},
                                },
                                "definition": ["test def"],
                            }
                        ],
                    }
                ],
            }
        }
    )
    entries = _convert_entries(v2_obj)
    assert len(entries) == 1
    source_features = [f for f in entries[0].features if f.type == "source"]
    assert len(source_features) == 1
    assert source_features[0].qualifiers["organism"] == ["Test"]
    assert source_features[0].qualifiers["ff_definition"] == ["test def"]


def test_convert_entries_features_mapped_by_sequence_id() -> None:
    v2_obj = _make_v2_minimal(
        {
            "sequences": {
                "common_source": {"organism": "Test", "mol_type": "genomic DNA"},
                "entries": [
                    {
                        "id": "chr1",
                        "name": "chr1",
                        "type": "chromosome",
                        "topology": "linear",
                        "source_features": [{"id": "sf1", "location": "1..100"}],
                    }
                ],
            },
            "features": [
                {
                    "id": "f1",
                    "type": "CDS",
                    "location": "10..50",
                    "sequence_id": "chr1",
                    "qualifiers": {"product": [{"value": "test protein"}]},
                }
            ],
        }
    )
    entries = _convert_entries(v2_obj)
    cds_features = [f for f in entries[0].features if f.type == "CDS"]
    assert len(cds_features) == 1
    assert cds_features[0].qualifiers["product"] == ["test protein"]


def test_convert_entries_comment_feature_from_entry_comments() -> None:
    v2_obj = _make_v2_minimal(
        {
            "sequences": {
                "common_source": {"organism": "Test", "mol_type": "genomic DNA"},
                "entries": [
                    {
                        "id": "chr1",
                        "name": "chr1",
                        "type": "chromosome",
                        "topology": "linear",
                        "comments": [["comment line 1"]],
                        "source_features": [{"id": "sf1", "location": "1..100"}],
                    }
                ],
            }
        }
    )
    entries = _convert_entries(v2_obj)
    comment_features = [f for f in entries[0].features if f.type == "COMMENT"]
    assert len(comment_features) == 1
    assert comment_features[0].qualifiers["line"] == ["comment line 1"]


# === BUG-C1: COMMENT feature type is uppercase ===


def test_convert_entries_comment_feature_type_is_uppercase() -> None:
    v2_obj = _make_v2_minimal(
        {
            "sequences": {
                "common_source": {"organism": "Test", "mol_type": "genomic DNA"},
                "entries": [
                    {
                        "id": "chr1",
                        "name": "chr1",
                        "type": "chromosome",
                        "topology": "linear",
                        "comments": [["comment line 1"]],
                        "source_features": [{"id": "sf1", "location": "1..100"}],
                    }
                ],
            }
        }
    )
    entries = _convert_entries(v2_obj)
    comment_features = [f for f in entries[0].features if f.type == "COMMENT"]
    assert len(comment_features) == 1
    assert comment_features[0].type == "COMMENT"


def test_comment_roundtrip_v1_v2_v1_preserves_comments() -> None:
    v2_obj = _make_v2_minimal(
        {
            "sequences": {
                "common_source": {"organism": "Test", "mol_type": "genomic DNA"},
                "entries": [
                    {
                        "id": "chr1",
                        "name": "chr1",
                        "type": "chromosome",
                        "topology": "linear",
                        "comments": [["line1", "line2"]],
                        "source_features": [{"id": "sf1", "location": "1..100"}],
                    }
                ],
            }
        }
    )
    v1_obj = v2_to_v1(v2_obj)
    v2_back = v1_to_v2(v1_obj)
    assert v2_back.sequences.entries[0].comments == [["line1", "line2"]]


# === data loss documentation (xfail) ===


def test_v2_to_v1_data_loss_orcid_warns() -> None:
    v2_obj = _make_v2_minimal(
        {
            "submission": {
                "submitters": [
                    {
                        "name": "Test",
                        "abbreviation": "T,T.",
                        "email": "t@t.com",
                        "orcid": "0000-0000-0000-0001",
                        "organization": [
                            {"name": "I", "type": "institution", "address": {"country": "JP", "city": "T"}}
                        ],
                    }
                ],
                "references": [{"title": "T", "authors": [], "status": "unpublished", "year": "2025"}],
            }
        }
    )
    with pytest.warns(UserWarning, match="orcid"):
        v2_to_v1(v2_obj)


def test_v2_to_v1_data_loss_ror_id_warns() -> None:
    v2_obj = _make_v2_minimal(
        {
            "submission": {
                "submitters": [
                    {
                        "name": "Test",
                        "abbreviation": "T,T.",
                        "email": "t@t.com",
                        "organization": [
                            {
                                "name": "I",
                                "type": "institution",
                                "ror_id": "https://ror.org/01xq5f0",
                                "address": {"country": "JP", "city": "T"},
                            }
                        ],
                    }
                ],
                "references": [{"title": "T", "authors": [], "status": "unpublished", "year": "2025"}],
            }
        }
    )
    with pytest.warns(UserWarning, match="ror_id"):
        v2_to_v1(v2_obj)


def test_v2_to_v1_data_loss_doi_warns() -> None:
    v2_obj = _make_v2_minimal(
        {
            "submission": {
                "submitters": [
                    {
                        "name": "T",
                        "abbreviation": "T,T.",
                        "email": "t@t.com",
                        "organization": [
                            {"name": "I", "type": "institution", "address": {"country": "JP", "city": "T"}}
                        ],
                    }
                ],
                "references": [
                    {
                        "title": "T",
                        "authors": [],
                        "status": "published",
                        "year": "2025",
                        "doi": "10.1038/nature12345",
                    }
                ],
            }
        }
    )
    with pytest.warns(UserWarning, match="doi"):
        v2_to_v1(v2_obj)


def test_v2_to_v1_data_loss_journal_warns() -> None:
    v2_obj = _make_v2_minimal(
        {
            "submission": {
                "submitters": [
                    {
                        "name": "T",
                        "abbreviation": "T,T.",
                        "email": "t@t.com",
                        "organization": [
                            {"name": "I", "type": "institution", "address": {"country": "JP", "city": "T"}}
                        ],
                    }
                ],
                "references": [
                    {"title": "T", "authors": [], "status": "published", "year": "2025", "journal": "Nature"}
                ],
            }
        }
    )
    with pytest.warns(UserWarning, match="journal"):
        v2_to_v1(v2_obj)


def test_v2_to_v1_data_loss_volume_issue_pages_warns() -> None:
    v2_obj = _make_v2_minimal(
        {
            "submission": {
                "submitters": [
                    {
                        "name": "T",
                        "abbreviation": "T,T.",
                        "email": "t@t.com",
                        "organization": [
                            {"name": "I", "type": "institution", "address": {"country": "JP", "city": "T"}}
                        ],
                    }
                ],
                "references": [
                    {
                        "title": "T",
                        "authors": [],
                        "status": "published",
                        "year": "2025",
                        "volume": "8",
                        "issue": "1",
                        "start_page": "15",
                        "end_page": "20",
                    }
                ],
            }
        }
    )
    with pytest.warns(UserWarning, match="volume|issue|page"):
        v2_to_v1(v2_obj)


def test_v2_to_v1_data_loss_multiple_institutions_warns() -> None:
    v2_obj = _make_v2_minimal(
        {
            "submission": {
                "submitters": [
                    {
                        "name": "T",
                        "abbreviation": "T,T.",
                        "email": "t@t.com",
                        "organization": [
                            {"name": "Inst1", "type": "institution", "address": {"country": "JP", "city": "T"}},
                            {"name": "Inst2", "type": "institution", "address": {"country": "US", "city": "N"}},
                        ],
                    }
                ],
                "references": [{"title": "T", "authors": [], "status": "unpublished", "year": "2025"}],
            }
        }
    )
    with pytest.warns(UserWarning, match="institution"):
        v2_to_v1(v2_obj)


def test_v2_to_v1_data_loss_multiple_consortiums_warns() -> None:
    v2_obj = _make_v2_minimal(
        {
            "submission": {
                "submitters": [
                    {
                        "name": "T",
                        "abbreviation": "T,T.",
                        "email": "t@t.com",
                        "organization": [
                            {"name": "Inst", "type": "institution", "address": {"country": "JP", "city": "T"}},
                            {"name": "Con1", "type": "consortium"},
                            {"name": "Con2", "type": "consortium"},
                        ],
                    }
                ],
                "references": [{"title": "T", "authors": [], "status": "unpublished", "year": "2025"}],
            }
        }
    )
    with pytest.warns(UserWarning, match="consortium"):
        v2_to_v1(v2_obj)


def test_v2_to_v1_data_loss_non_st_comment_experiment_warns() -> None:
    v2_obj = _make_v2_minimal(
        {
            "experiments": [
                {
                    "id": "st_comment_experiment",
                    "platform": {"platform_type": "Illumina"},
                    "experiment_attributes": {"tagset_id": "Genome-Assembly-Data", "assembly_method": "test"},
                },
                {
                    "id": "custom_experiment",
                    "platform": {"platform_type": "PacBio"},
                    "experiment_attributes": {},
                },
            ]
        }
    )
    with pytest.warns(UserWarning, match="experiment"):
        v2_to_v1(v2_obj)


def test_v2_to_v1_data_loss_person_name_without_abbr_warns() -> None:
    v2_obj = _make_v2_minimal(
        {
            "submission": {
                "submitters": [
                    {
                        "name": "Only Name No Abbr",
                        "email": "only@example.com",
                        "organization": [
                            {"name": "I", "type": "institution", "address": {"country": "JP", "city": "T"}}
                        ],
                    }
                ],
                "references": [{"title": "T", "authors": [], "status": "unpublished", "year": "2025"}],
            }
        }
    )
    with pytest.warns(UserWarning, match="abbreviation"):
        v2_to_v1(v2_obj)


def test_v2_to_v1_data_loss_unknown_xref_db_warns() -> None:
    v2_obj = _make_v2_minimal(
        {
            "submission": {
                "submitters": [
                    {
                        "name": "T",
                        "abbreviation": "T,T.",
                        "email": "t@t.com",
                        "organization": [
                            {"name": "I", "type": "institution", "address": {"country": "JP", "city": "T"}}
                        ],
                    }
                ],
                "db_xrefs": [
                    {"db": "bioproject", "id": "PRJDB99999"},
                    {"db": "custom_db", "id": "CUSTOM001"},
                ],
                "references": [{"title": "T", "authors": [], "status": "unpublished", "year": "2025"}],
            }
        }
    )
    with pytest.warns(UserWarning, match="custom_db"):
        v2_to_v1(v2_obj)


def test_v2_to_v1_data_loss_source_format_warns() -> None:
    v2_obj = _make_v2_minimal({"provenance": {"source_format": "GFF"}})
    with pytest.warns(UserWarning, match="source_format"):
        v2_to_v1(v2_obj)


# === default value warnings ===


def test_v2_to_v1_trad_submission_category_none_warns() -> None:
    v2_obj = _make_v2_minimal()
    assert v2_obj.submission.trad_submission_category is None
    with pytest.warns(UserWarning, match="trad_submission_category"):
        _convert_common(v2_obj)


def test_v2_to_v1_division_none_warns() -> None:
    v2_obj = _make_v2_minimal()
    assert v2_obj.submission.division is None
    with pytest.warns(UserWarning, match="division"):
        _convert_common_meta(v2_obj)


# === edge case tests ===


def test_convert_common_submitters_empty_list() -> None:
    v2_obj = _make_v2_minimal(
        {
            "submission": {
                "submitters": [],
                "references": [{"title": "T", "authors": [], "status": "unpublished", "year": "2025"}],
            }
        }
    )
    common = _convert_common(v2_obj)
    assert common.SUBMITTER.contact == ""
    assert common.SUBMITTER.email == ""
    assert common.SUBMITTER.ab_name == []


def test_convert_common_multiple_institutions_first_only_preserved() -> None:
    v2_obj = _make_v2_minimal(
        {
            "submission": {
                "submitters": [
                    {
                        "name": "T",
                        "abbreviation": "T,T.",
                        "email": "t@t.com",
                        "organization": [
                            {"name": "First Inst", "type": "institution", "address": {"country": "JP", "city": "T"}},
                            {"name": "Second Inst", "type": "institution", "address": {"country": "US", "city": "N"}},
                        ],
                    }
                ],
                "references": [{"title": "T", "authors": [], "status": "unpublished", "year": "2025"}],
            }
        }
    )
    with pytest.warns(UserWarning, match="institution"):
        common = _convert_common(v2_obj)
    assert common.SUBMITTER.institute == "First Inst"
    assert common.SUBMITTER.country == "JP"


def test_convert_common_multiple_consortiums_last_preserved() -> None:
    v2_obj = _make_v2_minimal(
        {
            "submission": {
                "submitters": [
                    {
                        "name": "T",
                        "abbreviation": "T,T.",
                        "email": "t@t.com",
                        "organization": [
                            {"name": "Inst", "type": "institution", "address": {"country": "JP", "city": "T"}},
                            {"name": "Con1", "type": "consortium"},
                            {"name": "Con2", "type": "consortium"},
                        ],
                    }
                ],
                "references": [{"title": "T", "authors": [], "status": "unpublished", "year": "2025"}],
            }
        }
    )
    with pytest.warns(UserWarning, match="consortium"):
        common = _convert_common(v2_obj)
    assert common.SUBMITTER.consrtm == "Con2"


def test_qualifier_boolean_roundtrip() -> None:
    """Boolean qualifier values survive v2->v1->v2 roundtrip."""
    v2_obj = _make_v2_minimal(
        {
            "sequences": {
                "common_source": {
                    "organism": "Test",
                    "mol_type": "genomic DNA",
                    "qualifiers": {"focus": [{"value": "true"}]},
                }
            }
        }
    )
    v1_obj = v2_to_v1(v2_obj)
    # v1 should have bool True
    assert v1_obj.COMMON_SOURCE.model_extra is not None
    assert v1_obj.COMMON_SOURCE.model_extra["focus"] is True
    # Round back to v2
    v2_back = v1_to_v2(v1_obj)
    assert v2_back.sequences.common_source.qualifiers["focus"][0].value == "true"
