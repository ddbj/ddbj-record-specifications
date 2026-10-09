import warnings
from typing import Any

import pytest

from ddbj_record.converter.v2_to_v3 import (
    ST_COMMENT_EXPERIMENT_ID,
    _convert_experiments,
    _convert_features,
    _convert_projects,
    _convert_provenance,
    _convert_relations,
    _convert_sequences,
    _convert_submission,
    v2_to_v3,
)
from ddbj_record.schema.v2 import DdbjRecord as DdbjRecordV2
from ddbj_record.schema.v3 import DdbjRecord as DdbjRecordV3
from ddbj_record.schema.v3 import Qualifier

# === fixture の一致 ===


def test_v2_to_v3_fixture_matches_expected(v2_to_v3_input: dict[str, Any], v2_to_v3_expected: dict[str, Any]) -> None:
    result = v2_to_v3(DdbjRecordV2.model_validate(v2_to_v3_input))
    assert result.model_dump(exclude_none=True, by_alias=True) == v2_to_v3_expected


def test_v2_to_v3_fixture_converts_without_warnings(v2_to_v3_input: dict[str, Any]) -> None:
    # 入力の fixture には、v3 に置き場の無いものを入れていない。
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        v2_to_v3(DdbjRecordV2.model_validate(v2_to_v3_input))


def test_v2_to_v3_output_schema_version(v2_to_v3_input: dict[str, Any]) -> None:
    assert v2_to_v3(DdbjRecordV2.model_validate(v2_to_v3_input)).schema_version == "v3"


def test_v2_to_v3_output_is_valid_v3(v2_to_v3_input: dict[str, Any]) -> None:
    result = v2_to_v3(DdbjRecordV2.model_validate(v2_to_v3_input))
    DdbjRecordV3.model_validate(result.model_dump(exclude_none=True, by_alias=True))


# === 全ての v2 の fixture ===
#
# 実データから作った v2 の fixture (空文字列の submitter や organism を含む) も、全て v3 に変換でき、
# 変換結果が v3 の型で読める。

V2_FIXTURES = [
    "v2_valid_minimal",
    "v2_valid_dfc_gnm",
    "v2_valid_wf_dfc_wgs",
    "v2_valid_dfv",
    "v2_valid_wf_dfv",
    "v2_valid_boolean_qualifier",
    "v2_valid_complex_location",
    "v2_valid_multi_source",
    "v2_valid_wgs_with_keyword",
    "v2_to_v1_input",
]


def _convert_fixture(fixture_name: str, request: pytest.FixtureRequest) -> tuple[DdbjRecordV2, DdbjRecordV3]:
    v2_obj = DdbjRecordV2.model_validate(request.getfixturevalue(fixture_name))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return v2_obj, v2_to_v3(v2_obj)


@pytest.mark.parametrize("fixture_name", V2_FIXTURES)
def test_every_v2_fixture_converts_to_v3_that_reads_back_unchanged(
    fixture_name: str, request: pytest.FixtureRequest
) -> None:
    _, v3_obj = _convert_fixture(fixture_name, request)
    dumped = v3_obj.model_dump(exclude_none=True, by_alias=True)
    assert DdbjRecordV3.model_validate(dumped).model_dump(exclude_none=True, by_alias=True) == dumped


@pytest.mark.parametrize("fixture_name", V2_FIXTURES)
def test_every_v2_fixture_keeps_entries_in_order(fixture_name: str, request: pytest.FixtureRequest) -> None:
    v2_obj, v3_obj = _convert_fixture(fixture_name, request)
    assert v3_obj.sequences is not None
    v3_entries = v3_obj.sequences.entries or []
    assert [e.alias for e in v3_entries] == [e.id for e in v2_obj.sequences.entries]
    for v2_entry, v3_entry in zip(v2_obj.sequences.entries, v3_entries, strict=True):
        assert v3_entry.sequence == v2_entry.sequence
        assert len(v3_entry.source_features or []) == len(v2_entry.source_features)


@pytest.mark.parametrize("fixture_name", V2_FIXTURES)
def test_every_v2_fixture_keeps_features_in_order(fixture_name: str, request: pytest.FixtureRequest) -> None:
    v2_obj, v3_obj = _convert_fixture(fixture_name, request)
    v3_features = v3_obj.features or []
    assert [(f.alias, f.sequence_id, f.type) for f in v3_features] == [
        (f.id, f.sequence_id, f.type) for f in v2_obj.features
    ]


@pytest.mark.parametrize("fixture_name", V2_FIXTURES)
def test_every_v2_fixture_keeps_common_source(fixture_name: str, request: pytest.FixtureRequest) -> None:
    v2_obj, v3_obj = _convert_fixture(fixture_name, request)
    assert v3_obj.sequences is not None
    assert v3_obj.sequences.common_source is not None
    assert v3_obj.sequences.common_source.organism is not None
    assert v3_obj.sequences.common_source.organism.name == v2_obj.sequences.common_source.organism
    assert v3_obj.sequences.common_source.mol_type == v2_obj.sequences.common_source.mol_type


# === 単体 ===


def _make_v2(overrides: dict[str, Any] | None = None) -> DdbjRecordV2:
    base: dict[str, Any] = {
        "schema_version": "v2.3",
        "provenance": {},
        "submission": {
            "submitters": [{"name": "Hanako Mishima", "abbreviation": "Mishima,H.", "email": "mishima@ddbj.nig.ac.jp"}],
            "db_xrefs": [],
            "references": [],
            "comments": [],
            "trad_submission_category": "GNM",
            "division": "BCT",
        },
        "experiments": [],
        "sequences": {
            "common_source": {"organism": "Test organism", "mol_type": "genomic DNA", "qualifiers": {}},
            "entries": [],
        },
        "features": [],
    }
    for key, value in (overrides or {}).items():
        keys = key.split(".")
        target = base
        for k in keys[:-1]:
            target = target[k]
        target[keys[-1]] = value
    return DdbjRecordV2.model_validate(base)


def _entry(entry_id: str, **extra: Any) -> dict[str, Any]:
    return {
        "id": entry_id,
        "name": entry_id,
        "type": "chromosome",
        "topology": "circular",
        "source_features": [{"id": f"sf_{entry_id}", "location": "1..4"}],
        **extra,
    }


def _reference(**extra: Any) -> dict[str, Any]:
    return {"title": "Test", "authors": [{"abbreviation": "T,T."}], "status": "unpublished", "year": "2025", **extra}


# --- provenance ---


def test_provenance_keeps_source_format_and_extra_keys() -> None:
    v2_obj = _make_v2({"provenance": {"source_format": "TradAnnotation", "dfast_version": "1.3.4"}})
    provenance = _convert_provenance(v2_obj)
    assert provenance is not None
    assert provenance.source_format == "TradAnnotation"
    assert provenance.model_extra == {"dfast_version": "1.3.4"}


def test_provenance_takes_submission_category_from_trad_submission_category() -> None:
    provenance = _convert_provenance(_make_v2({"submission.trad_submission_category": "WGS"}))
    assert provenance is not None
    assert provenance.submission_category == "WGS"


def test_provenance_is_omitted_when_empty() -> None:
    assert _convert_provenance(_make_v2({"submission.trad_submission_category": None})) is None


# --- submission ---


def test_submission_first_submitter_is_contact_and_the_rest_are_submitters() -> None:
    v2_obj = _make_v2(
        {"submission.submitters": [{"abbreviation": "A,A."}, {"abbreviation": "B,B."}, {"abbreviation": "C,C."}]}
    )
    submission = _convert_submission(v2_obj.submission)
    assert submission is not None
    assert submission.submitters is not None
    assert [(p.abbreviation, p.role) for p in submission.submitters] == [
        ("A,A.", "contact"),
        ("B,B.", "submitter"),
        ("C,C.", "submitter"),
    ]


def test_submission_person_fields_and_organizations_are_kept() -> None:
    v2_obj = _make_v2(
        {
            "submission.submitters": [
                {
                    "name": "Hanako Mishima",
                    "abbreviation": "Mishima,H.",
                    "email": "mishima@ddbj.nig.ac.jp",
                    "orcid": "0000-0000-0000-0001",
                    "organization": [
                        {
                            "name": "NIG",
                            "type": "institution",
                            "department": "DDBJ",
                            "url": "https://ddbj.nig.ac.jp",
                            "ror_id": "https://ror.org/01xq5f0",
                            "address": {"country": "Japan", "city": "Mishima", "postal_code": "411-8540"},
                        },
                        {"name": "Consortium X", "type": "consortium"},
                    ],
                }
            ]
        }
    )
    submission = _convert_submission(v2_obj.submission)
    assert submission is not None
    assert submission.submitters is not None
    person = submission.submitters[0]
    assert (person.name, person.abbreviation, person.email, person.orcid) == (
        "Hanako Mishima",
        "Mishima,H.",
        "mishima@ddbj.nig.ac.jp",
        "0000-0000-0000-0001",
    )
    assert person.organizations is not None
    institution, consortium = person.organizations
    assert (institution.name, institution.type, institution.department, institution.url, institution.ror_id) == (
        "NIG",
        "institution",
        "DDBJ",
        "https://ddbj.nig.ac.jp",
        "https://ror.org/01xq5f0",
    )
    assert institution.address is not None
    assert (institution.address.country, institution.address.city, institution.address.postal_code) == (
        "Japan",
        "Mishima",
        "411-8540",
    )
    assert institution.address.state is None
    assert (consortium.name, consortium.type) == ("Consortium X", "consortium")


def test_submission_empty_organization_list_becomes_none() -> None:
    v2_obj = _make_v2({"submission.submitters": [{"abbreviation": "A,A.", "organization": []}]})
    submission = _convert_submission(v2_obj.submission)
    assert submission is not None
    assert submission.submitters is not None
    assert submission.submitters[0].organizations is None


def test_submission_comment_lines_are_joined_into_one_string() -> None:
    v2_obj = _make_v2({"submission.comments": [["line1", "line2"], ["single"]]})
    submission = _convert_submission(v2_obj.submission)
    assert submission is not None
    assert submission.comments == ["line1\nline2", "single"]


def test_submission_comment_without_lines_is_dropped() -> None:
    v2_obj = _make_v2({"submission.comments": [[], ["kept"]]})
    submission = _convert_submission(v2_obj.submission)
    assert submission is not None
    assert submission.comments == ["kept"]


def test_submission_hold_date_is_kept_as_is() -> None:
    submission = _convert_submission(_make_v2({"submission.hold_date": "2025-03-31"}).submission)
    assert submission is not None
    assert submission.hold_date == "2025-03-31"


def test_submission_is_omitted_when_empty() -> None:
    assert _convert_submission(_make_v2({"submission.submitters": []}).submission) is None


# --- projects ---


def test_projects_omitted_without_references_and_locus_tag_prefix() -> None:
    assert _convert_projects(_make_v2().submission) is None


def test_projects_is_one_project_without_accession() -> None:
    projects = _convert_projects(_make_v2({"submission.locus_tag_prefix": "PLH"}).submission)
    assert projects is not None
    assert len(projects) == 1
    assert projects[0].accession is None
    assert projects[0].locus_tag_prefix is not None
    assert [p.prefix for p in projects[0].locus_tag_prefix] == ["PLH"]
    assert projects[0].locus_tag_prefix[0].biosample_id is None


def test_publication_date_comes_from_year_without_date_published() -> None:
    projects = _convert_projects(_make_v2({"submission.references": [_reference(year="2023")]}).submission)
    assert projects is not None
    assert projects[0].publications is not None
    assert projects[0].publications[0].date == "2023"


def test_publication_date_prefers_date_published() -> None:
    reference = _reference(year="2024", date_published="2024-03-15")
    projects = _convert_projects(_make_v2({"submission.references": [reference]}).submission)
    assert projects is not None
    assert projects[0].publications is not None
    assert projects[0].publications[0].date == "2024-03-15"


def test_publication_date_is_none_for_empty_year() -> None:
    projects = _convert_projects(_make_v2({"submission.references": [_reference(year="")]}).submission)
    assert projects is not None
    assert projects[0].publications is not None
    assert projects[0].publications[0].date is None


def test_publication_year_differing_from_date_published_warns() -> None:
    reference = _reference(year="2023", date_published="2024-03-15")
    with pytest.warns(UserWarning, match="year '2023' differs from date_published"):
        projects = _convert_projects(_make_v2({"submission.references": [reference]}).submission)
    assert projects is not None
    assert projects[0].publications is not None
    assert projects[0].publications[0].date == "2024-03-15"


def test_publication_pages_and_identifiers_are_renamed() -> None:
    reference = _reference(
        status="published",
        journal="J",
        volume="1",
        issue="2",
        start_page="10",
        end_page="20",
        doi="10.1/x",
        pubmed_id="123",
        url="https://example.org/x",
    )
    projects = _convert_projects(_make_v2({"submission.references": [reference]}).submission)
    assert projects is not None
    assert projects[0].publications is not None
    publication = projects[0].publications[0]
    assert (publication.status, publication.journal, publication.volume, publication.issue) == (
        "published",
        "J",
        "1",
        "2",
    )
    assert (publication.pages_from, publication.pages_to) == ("10", "20")
    assert (publication.doi, publication.pubmed_id, publication.url) == ("10.1/x", "123", "https://example.org/x")


def test_publication_authors_keep_name_and_abbreviation_without_role() -> None:
    reference = _reference(authors=[{"name": "Taro Yamada", "abbreviation": "Yamada,T."}])
    projects = _convert_projects(_make_v2({"submission.references": [reference]}).submission)
    assert projects is not None
    assert projects[0].publications is not None
    authors = projects[0].publications[0].authors
    assert authors is not None
    assert (authors[0].name, authors[0].abbreviation, authors[0].role) == ("Taro Yamada", "Yamada,T.", None)


def test_publication_consortiums_become_names() -> None:
    reference = _reference(consortiums=[{"name": "Consortium X"}, {"name": "Consortium Y"}])
    projects = _convert_projects(_make_v2({"submission.references": [reference]}).submission)
    assert projects is not None
    assert projects[0].publications is not None
    assert projects[0].publications[0].consortiums == ["Consortium X", "Consortium Y"]


def test_publication_consortium_with_more_than_a_name_warns() -> None:
    reference = _reference(consortiums=[{"name": "Consortium X", "url": "https://example.org"}])
    with pytest.warns(UserWarning, match="consortium 'Consortium X'"):
        _convert_projects(_make_v2({"submission.references": [reference]}).submission)


def test_publication_consortium_with_only_a_name_does_not_warn() -> None:
    reference = _reference(consortiums=[{"name": "Consortium X"}])
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        _convert_projects(_make_v2({"submission.references": [reference]}).submission)


# --- relations ---


def test_relations_are_xrefs_without_source() -> None:
    v2_obj = _make_v2(
        {"submission.db_xrefs": [{"db": "bioproject", "id": "PRJDB1"}, {"db": "biosample", "id": "SAMD1"}]}
    )
    relations = _convert_relations(v2_obj.submission.db_xrefs)
    assert relations is not None
    assert [
        (r.type, r.source, r.target.db if r.target else None, r.target.id if r.target else None) for r in relations
    ] == [
        ("xref", None, "bioproject", "PRJDB1"),
        ("xref", None, "biosample", "SAMD1"),
    ]


def test_relations_omitted_without_db_xrefs() -> None:
    assert _convert_relations([]) is None


# --- experiments ---


def _st_comment_experiment(**extra: Any) -> dict[str, Any]:
    return {
        "id": ST_COMMENT_EXPERIMENT_ID,
        "platform": {"platform_type": "Illumina MiSeq"},
        "experiment_attributes": {
            "tagset_id": "Genome-Assembly-Data",
            "assembly_method": "SPAdes v. 3.15.5",
            "genome_coverage": "60x",
        },
        **extra,
    }


def test_st_comment_experiment_becomes_a_structured_comment_with_mss_field_names() -> None:
    structured_comments, experiments = _convert_experiments(
        _make_v2({"experiments": [_st_comment_experiment()]}).experiments
    )
    assert experiments is None
    assert structured_comments is not None
    assert structured_comments[0].tagset_id == "Genome-Assembly-Data"
    assert structured_comments[0].fields == {
        "Assembly Method": "SPAdes v. 3.15.5",
        "Genome Coverage": "60x",
        "Sequencing Technology": "Illumina MiSeq",
    }


def test_st_comment_coverage_is_renamed() -> None:
    experiment = _st_comment_experiment(
        experiment_attributes={"tagset_id": "Genome-Assembly-Data", "assembly_method": "x", "coverage": "100x"}
    )
    structured_comments, _ = _convert_experiments(_make_v2({"experiments": [experiment]}).experiments)
    assert structured_comments is not None
    assert structured_comments[0].fields is not None
    assert structured_comments[0].fields["Coverage"] == "100x"


def test_st_comment_unknown_attribute_key_is_kept_as_written() -> None:
    experiment = _st_comment_experiment(experiment_attributes={"tagset_id": "T", "sequencing_technology": "x"})
    structured_comments, _ = _convert_experiments(_make_v2({"experiments": [experiment]}).experiments)
    assert structured_comments is not None
    assert structured_comments[0].fields is not None
    assert structured_comments[0].fields["sequencing_technology"] == "x"


def test_st_comment_without_platform_has_no_sequencing_technology() -> None:
    experiment = _st_comment_experiment()
    del experiment["platform"]
    structured_comments, _ = _convert_experiments(_make_v2({"experiments": [experiment]}).experiments)
    assert structured_comments is not None
    assert structured_comments[0].fields is not None
    assert "Sequencing Technology" not in structured_comments[0].fields


def test_st_comment_with_only_tagset_id_has_no_fields() -> None:
    experiment = _st_comment_experiment(experiment_attributes={"tagset_id": "T"})
    del experiment["platform"]
    structured_comments, _ = _convert_experiments(_make_v2({"experiments": [experiment]}).experiments)
    assert structured_comments is not None
    assert structured_comments[0].fields is None


def test_st_comment_experiment_title_and_design_warn() -> None:
    experiment = _st_comment_experiment(title="t", design={"library_name": "lib"})
    with (
        pytest.warns(UserWarning, match="title of st_comment_experiment"),
        pytest.warns(UserWarning, match="design of"),
    ):
        _convert_experiments(_make_v2({"experiments": [experiment]}).experiments)


def test_st_comment_experiment_instrument_model_warns() -> None:
    experiment = _st_comment_experiment(platform={"platform_type": "x", "instrument_model": "y"})
    with pytest.warns(UserWarning, match="instrument_model of st_comment_experiment"):
        _convert_experiments(_make_v2({"experiments": [experiment]}).experiments)


def test_other_experiment_moves_design_fields_to_library_and_lowercases_layout() -> None:
    experiment = {
        "id": "exp-1",
        "title": "t",
        "design": {
            "design_description": "d",
            "library_name": "lib1",
            "library_strategy": "WGS",
            "library_source": "GENOMIC",
            "library_selection": "RANDOM",
            "library_layout": {"layout_type": "SINGLE", "nominal_length": 300, "nominal_sdev": 50.0},
            "pooling_strategy": "none",
            "library_construction_protocol": "p",
            "targeted_loci": [{"locus_name": "16S rRNA", "description": "V3-V4"}],
        },
        "platform": {"platform_type": "ILLUMINA", "instrument_model": "Illumina MiSeq"},
        "experiment_attributes": {"k": "v"},
    }
    structured_comments, experiments = _convert_experiments(_make_v2({"experiments": [experiment]}).experiments)
    assert structured_comments is None
    assert experiments is not None
    converted = experiments[0]
    assert (converted.alias, converted.title, converted.description) == ("exp-1", "t", "d")
    assert converted.library is not None
    assert (
        converted.library.name,
        converted.library.strategy,
        converted.library.source,
        converted.library.selection,
    ) == (
        "lib1",
        "WGS",
        "GENOMIC",
        "RANDOM",
    )
    assert (converted.library.layout, converted.library.nominal_length, converted.library.nominal_sdev) == (
        "single",
        300,
        50.0,
    )
    assert (converted.library.pooling_strategy, converted.library.construction_protocol) == ("none", "p")
    assert converted.platform is not None
    assert (converted.platform.type, converted.platform.instrument_model) == ("ILLUMINA", "Illumina MiSeq")
    assert converted.targeted_loci is not None
    assert (converted.targeted_loci[0].name, converted.targeted_loci[0].description) == ("16S rRNA", "V3-V4")
    assert converted.attributes is not None
    assert (converted.attributes[0].name, converted.attributes[0].value) == ("k", "v")


def test_other_experiment_without_design_and_platform_has_only_alias() -> None:
    _, experiments = _convert_experiments(
        _make_v2({"experiments": [{"id": "exp-1", "experiment_attributes": {}}]}).experiments
    )
    assert experiments is not None
    assert experiments[0].model_dump(exclude_none=True) == {"alias": "exp-1"}


def test_other_experiment_blank_attribute_name_is_dropped_with_warning() -> None:
    experiment = {"id": "exp-1", "experiment_attributes": {" ": "v", "k": "v"}}
    with pytest.warns(UserWarning, match="blank name"):
        _, experiments = _convert_experiments(_make_v2({"experiments": [experiment]}).experiments)
    assert experiments is not None
    assert experiments[0].attributes is not None
    assert [a.name for a in experiments[0].attributes] == ["k"]


def test_experiments_of_both_kinds_are_split() -> None:
    experiments_v2 = [_st_comment_experiment(), {"id": "exp-1", "experiment_attributes": {}}]
    structured_comments, experiments = _convert_experiments(_make_v2({"experiments": experiments_v2}).experiments)
    assert structured_comments is not None
    assert experiments is not None
    assert len(structured_comments) == 1
    assert [e.alias for e in experiments] == ["exp-1"]


def test_no_experiments_gives_none_for_both() -> None:
    assert _convert_experiments([]) == (None, None)


# --- sequences ---


def test_sequences_common_source_organism_becomes_organism_name() -> None:
    sequences = _convert_sequences(_make_v2(), None)
    assert sequences.common_source is not None
    assert sequences.common_source.organism is not None
    assert sequences.common_source.organism.name == "Test organism"
    assert sequences.common_source.organism.taxonomy_id is None
    assert sequences.common_source.mol_type == "genomic DNA"


def test_sequences_empty_qualifiers_become_none() -> None:
    sequences = _convert_sequences(_make_v2(), None)
    assert sequences.common_source is not None
    assert sequences.common_source.qualifiers is None


def test_sequences_qualifier_true_loses_its_value() -> None:
    v2_obj = _make_v2({"sequences.common_source.qualifiers": {"environmental_sample": [{"value": "true"}]}})
    sequences = _convert_sequences(v2_obj, None)
    assert sequences.common_source is not None
    assert sequences.common_source.qualifiers == {"environmental_sample": [Qualifier()]}


def test_sequences_qualifier_false_is_kept_as_written() -> None:
    v2_obj = _make_v2({"sequences.common_source.qualifiers": {"note": [{"value": "false"}]}})
    sequences = _convert_sequences(v2_obj, None)
    assert sequences.common_source is not None
    assert sequences.common_source.qualifiers == {"note": [Qualifier(value="false")]}


def test_sequences_qualifier_id_becomes_alias_and_values_keep_order() -> None:
    v2_obj = _make_v2(
        {"sequences.common_source.qualifiers": {"note": [{"id": "q1", "value": "first"}, {"value": "second"}]}}
    )
    sequences = _convert_sequences(v2_obj, None)
    assert sequences.common_source is not None
    assert sequences.common_source.qualifiers == {
        "note": [Qualifier(alias="q1", value="first"), Qualifier(value="second")]
    }


def test_sequences_entry_fields_are_renamed_and_division_is_copied_to_every_entry() -> None:
    v2_obj = _make_v2({"sequences.entries": [_entry("chr", sequence="atgc"), _entry("p1", type="plasmid")]})
    sequences = _convert_sequences(v2_obj, None)
    assert sequences.entries is not None
    assert [(e.alias, e.name, e.type, e.topology, e.division) for e in sequences.entries] == [
        ("chr", "chr", "chromosome", "circular", "BCT"),
        ("p1", "p1", "plasmid", "circular", "BCT"),
    ]
    assert sequences.entries[0].sequence == "atgc"
    assert sequences.entries[0].completeness is None


def test_sequences_entry_division_is_none_when_v2_has_none() -> None:
    v2_obj = _make_v2({"submission.division": None, "sequences.entries": [_entry("chr")]})
    sequences = _convert_sequences(v2_obj, None)
    assert sequences.entries is not None
    assert sequences.entries[0].division is None


def test_sequences_entry_comments_are_joined() -> None:
    v2_obj = _make_v2({"sequences.entries": [_entry("chr", comments=[["a", "b"], []])]})
    sequences = _convert_sequences(v2_obj, None)
    assert sequences.entries is not None
    assert sequences.entries[0].comments == ["a\nb"]


def test_sequences_source_feature_is_renamed_and_source_is_converted() -> None:
    source_feature = {
        "id": "sf1",
        "location": "1..4",
        "source": {"organism": "Phage", "mol_type": "genomic RNA", "qualifiers": {"plasmid": [{"value": "p1"}]}},
        "definition": ["@@[organism]@@ DNA"],
    }
    v2_obj = _make_v2({"sequences.entries": [_entry("chr", source_features=[source_feature])]})
    sequences = _convert_sequences(v2_obj, None)
    assert sequences.entries is not None
    assert sequences.entries[0].source_features is not None
    converted = sequences.entries[0].source_features[0]
    assert (converted.alias, converted.location, converted.definition) == ("sf1", "1..4", ["@@[organism]@@ DNA"])
    assert converted.source is not None
    assert converted.source.organism is not None
    assert (converted.source.organism.name, converted.source.mol_type) == ("Phage", "genomic RNA")
    assert converted.source.qualifiers == {"plasmid": [Qualifier(value="p1")]}


def test_sequences_source_feature_without_source_stays_without_source() -> None:
    v2_obj = _make_v2({"sequences.entries": [_entry("chr")]})
    sequences = _convert_sequences(v2_obj, None)
    assert sequences.entries is not None
    assert sequences.entries[0].source_features is not None
    assert sequences.entries[0].source_features[0].source is None
    assert sequences.entries[0].source_features[0].definition is None


def test_sequences_keywords_and_seq_prefix_move_from_submission() -> None:
    v2_obj = _make_v2({"submission.keywords": ["WGS", "STANDARD_DRAFT"], "submission.seq_prefix": "contig"})
    sequences = _convert_sequences(v2_obj, None)
    assert sequences.keywords == ["WGS", "STANDARD_DRAFT"]
    assert sequences.seq_prefix == "contig"


def test_sequences_empty_keywords_become_none() -> None:
    assert _convert_sequences(_make_v2({"submission.keywords": []}), None).keywords is None


def test_sequences_takes_structured_comments_as_given() -> None:
    structured_comments, _ = _convert_experiments(_make_v2({"experiments": [_st_comment_experiment()]}).experiments)
    sequences = _convert_sequences(_make_v2(), structured_comments)
    assert sequences.structured_comments == structured_comments


def test_sequences_empty_entries_become_none() -> None:
    assert _convert_sequences(_make_v2(), None).entries is None


def test_datatype_equal_to_trad_submission_category_is_dropped_silently() -> None:
    v2_obj = _make_v2({"submission.trad_submission_category": "WGS", "submission.datatype": "WGS"})
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        _convert_sequences(v2_obj, None)


def test_datatype_differing_from_trad_submission_category_warns() -> None:
    v2_obj = _make_v2({"submission.trad_submission_category": "GNM", "submission.datatype": "WGS"})
    with pytest.warns(UserWarning, match="datatype 'WGS'"):
        _convert_sequences(v2_obj, None)


def test_datatype_none_does_not_warn() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        _convert_sequences(_make_v2(), None)


# --- features ---


def test_features_are_renamed_and_keep_qualifiers() -> None:
    feature = {
        "id": "f1",
        "type": "CDS",
        "location": "1..4",
        "sequence_id": "chr",
        "qualifiers": {"product": [{"value": "p"}], "pseudo": [{"value": "true"}]},
        "locus_tag_id": "00010",
    }
    features = _convert_features(_make_v2({"features": [feature]}).features)
    assert features is not None
    converted = features[0]
    assert (converted.alias, converted.type, converted.location, converted.sequence_id, converted.locus_tag_id) == (
        "f1",
        "CDS",
        "1..4",
        "chr",
        "00010",
    )
    assert converted.qualifiers == {"product": [Qualifier(value="p")], "pseudo": [Qualifier()]}
    assert (converted.source_tool, converted.score, converted.phase, converted.parent_ids) == (None, None, None, None)


def test_features_empty_qualifiers_become_none() -> None:
    feature = {"id": "f1", "type": "CDS", "location": "1..4", "sequence_id": "chr", "qualifiers": {}}
    features = _convert_features(_make_v2({"features": [feature]}).features)
    assert features is not None
    assert features[0].qualifiers is None


def test_features_omitted_when_empty() -> None:
    assert _convert_features([]) is None


# === record 全体 ===


def test_v2_to_v3_minimal_record_has_only_schema_version_and_sequences(v2_valid_minimal: dict[str, Any]) -> None:
    result = v2_to_v3(DdbjRecordV2.model_validate(v2_valid_minimal))
    assert result.model_dump(exclude_none=True, by_alias=True) == {
        "schema_version": "v3",
        "sequences": {
            "common_source": {"organism": {"name": "Paucilactobacillus hokkaidonensis"}, "mol_type": "genomic DNA"}
        },
    }


def test_v2_to_v3_boolean_qualifier_fixture_drops_true(v2_valid_boolean_qualifier: dict[str, Any]) -> None:
    result = v2_to_v3(DdbjRecordV2.model_validate(v2_valid_boolean_qualifier))
    assert result.features is not None
    pseudo = result.features[0].qualifiers
    assert pseudo is not None
    assert pseudo["pseudo"] == [Qualifier()]
    assert pseudo["product"] == [Qualifier(value="pseudo protein")]
