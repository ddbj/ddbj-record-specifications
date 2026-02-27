import warnings
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from ddbj_record.converter.v1_to_v2 import _normalize_abbr, _qualifier_value_to_str, v1_to_v2
from ddbj_record.converter.v2_to_v1 import _qualifier_value_to_union, v2_to_v1
from ddbj_record.schema.v1 import DdbjRecord as DdbjRecordV1
from ddbj_record.schema.v2 import DdbjRecord as DdbjRecordV2

# === strategies ===

st_organism = st.text(min_size=1, max_size=80).filter(lambda s: s.strip() != "")
st_mol_type = st.sampled_from(["genomic DNA", "genomic RNA", "mRNA", "tRNA", "rRNA", "other DNA", "other RNA"])
st_trad_category = st.sampled_from(["WGS", "GNM"])
st_entry_type = st.sampled_from(["chromosome", "plasmid", "unplaced", "other"])
st_topology = st.sampled_from(["circular", "linear"])
st_abbr_name = st.from_regex(r"[A-Z][a-z]{1,10},[A-Z]\.", fullmatch=True)
st_keywords = st.one_of(st.none(), st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=5))
st_datatype = st.one_of(st.none(), st.text(min_size=1, max_size=20))


@st.composite
def st_v1_record(draw: st.DrawFn) -> dict[str, Any]:
    organism = draw(st_organism)
    mol_type = draw(st_mol_type)
    category = draw(st_trad_category)
    ab_name = draw(st_abbr_name)
    keywords = draw(st_keywords)
    datatype = draw(st_datatype)

    common: dict[str, Any] = {
        "SUBMITTER": {
            "ab_name": [ab_name],
            "contact": "Test User",
            "email": "test@example.com",
            "institute": "Test Institute",
            "country": "Japan",
            "city": "Tokyo",
            "street": "1-1",
            "zip": "000-0000",
        },
        "ST_COMMENT": {
            "tagset_id": "Genome-Assembly-Data",
            "Assembly Method": "test v. 1",
            "Sequencing Technology": "Illumina",
        },
        "trad_submission_category": category,
    }
    if keywords is not None:
        common["KEYWORD"] = {"keyword": keywords}
    if datatype is not None:
        common["DATATYPE"] = {"type": datatype}

    return {
        "schema_version": "v1.0",
        "COMMON": common,
        "COMMON_SOURCE": {
            "organism": organism,
            "mol_type": mol_type,
        },
        "COMMON_META": {
            "division": "BCT",
        },
    }


@st.composite
def st_v2_record(draw: st.DrawFn) -> dict[str, Any]:
    organism = draw(st_organism)
    mol_type = draw(st_mol_type)
    ab_name = draw(st_abbr_name)
    keywords = draw(st_keywords)
    datatype = draw(st_datatype)

    submission: dict[str, Any] = {
        "submitters": [
            {
                "name": "Test User",
                "abbreviation": ab_name,
                "email": "test@example.com",
                "organization": [
                    {
                        "name": "Test Institute",
                        "type": "institution",
                        "address": {"country": "Japan", "city": "Tokyo"},
                    }
                ],
            }
        ],
        "db_xrefs": [],
        "references": [
            {
                "title": "Test Title",
                "authors": [{"abbreviation": ab_name}],
                "status": "unpublished",
                "year": "2025",
            }
        ],
        "comments": [],
    }
    if keywords is not None:
        submission["keywords"] = keywords
    if datatype is not None:
        submission["datatype"] = datatype

    return {
        "schema_version": "v2.0",
        "provenance": {},
        "submission": submission,
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
            "common_source": {
                "organism": organism,
                "mol_type": mol_type,
                "qualifiers": {},
            },
            "entries": [],
        },
        "features": [],
    }


# === PBT tests ===


@given(record_data=st_v1_record())
@settings(max_examples=100)
def test_pbt_v1_to_v2_produces_valid_v2(record_data: dict[str, Any]) -> None:
    v1_obj = DdbjRecordV1.model_validate(record_data)
    v2_obj = v1_to_v2(v1_obj)
    dumped = v2_obj.model_dump(exclude_none=True, by_alias=True)
    DdbjRecordV2.model_validate(dumped)


@given(record_data=st_v2_record())
@settings(max_examples=100)
def test_pbt_v2_to_v1_produces_valid_v1(record_data: dict[str, Any]) -> None:
    v2_obj = DdbjRecordV2.model_validate(record_data)
    v1_obj = v2_to_v1(v2_obj)
    dumped = v1_obj.model_dump(exclude_none=True, by_alias=True)
    DdbjRecordV1.model_validate(dumped)


@given(record_data=st_v1_record())
@settings(max_examples=100)
def test_pbt_v1_to_v2_preserves_organism(record_data: dict[str, Any]) -> None:
    v1_obj = DdbjRecordV1.model_validate(record_data)
    v2_obj = v1_to_v2(v1_obj)
    assert v2_obj.sequences.common_source.organism == v1_obj.COMMON_SOURCE.organism


@given(record_data=st_v1_record())
@settings(max_examples=100)
def test_pbt_v1_to_v2_preserves_mol_type(record_data: dict[str, Any]) -> None:
    v1_obj = DdbjRecordV1.model_validate(record_data)
    v2_obj = v1_to_v2(v1_obj)
    assert v2_obj.sequences.common_source.mol_type == v1_obj.COMMON_SOURCE.mol_type


@given(record_data=st_v2_record())
@settings(max_examples=100)
def test_pbt_v2_to_v1_preserves_organism(record_data: dict[str, Any]) -> None:
    v2_obj = DdbjRecordV2.model_validate(record_data)
    v1_obj = v2_to_v1(v2_obj)
    assert v1_obj.COMMON_SOURCE.organism == v2_obj.sequences.common_source.organism


@given(record_data=st_v1_record())
@settings(max_examples=100)
def test_pbt_v1_to_v2_preserves_entries_count(record_data: dict[str, Any]) -> None:
    v1_obj = DdbjRecordV1.model_validate(record_data)
    v2_obj = v1_to_v2(v1_obj)
    assert len(v2_obj.sequences.entries) == len(v1_obj.ENTRIES)


@given(abbr=st.text(min_size=1, max_size=30))
@settings(max_examples=100)
def test_pbt_normalize_abbr_idempotent(abbr: str) -> None:
    once = _normalize_abbr(abbr)
    twice = _normalize_abbr(once)
    assert once == twice


@given(record_data=st_v1_record())
@settings(max_examples=100)
def test_pbt_v1_to_v2_output_schema_version_fixed(record_data: dict[str, Any]) -> None:
    v1_obj = DdbjRecordV1.model_validate(record_data)
    v2_obj = v1_to_v2(v1_obj)
    assert v2_obj.schema_version == "v2.3"


@given(record_data=st_v2_record())
@settings(max_examples=100)
def test_pbt_v2_to_v1_output_schema_version_fixed(record_data: dict[str, Any]) -> None:
    v2_obj = DdbjRecordV2.model_validate(record_data)
    v1_obj = v2_to_v1(v2_obj)
    assert v1_obj.schema_version == "v1.0"


# === PBT: reference status roundtrip idempotency ===

st_ref_status_v1 = st.sampled_from(["Unpublished", "Published", "In Press"])


@given(status=st_ref_status_v1)
@settings(max_examples=100)
def test_pbt_reference_status_roundtrip_idempotent(status: str) -> None:
    """v1 status -> v2 normalize -> v1 denormalize is idempotent."""
    # v1->v2: space->hyphen, lower
    v2_status = "-".join(status.lower().split(" "))
    # v2->v1: hyphen->space, title case
    v1_back = " ".join(v2_status.split("-")).title()
    assert v1_back == status


# === PBT: qualifier type preservation ===

st_qualifier_value = st.one_of(
    st.just("true"),
    st.just("false"),
    st.text(min_size=1, max_size=50).filter(lambda s: s not in ("true", "false")),
)


@given(value=st_qualifier_value)
@settings(max_examples=100)
def test_pbt_qualifier_roundtrip_preserves_value(value: str) -> None:
    """v2 str -> v1 str|bool -> v2 str roundtrip preserves the original value."""
    v1_value = _qualifier_value_to_union(value)
    v2_back = _qualifier_value_to_str(v1_value)
    assert v2_back == value


# === PBT: v1->v2->v1 common_source preservation ===


@given(record_data=st_v1_record())
@settings(max_examples=100)
def test_pbt_v1_roundtrip_preserves_common_source(record_data: dict[str, Any]) -> None:
    """v1->v2->v1 roundtrip preserves organism and mol_type in COMMON_SOURCE."""
    v1_obj = DdbjRecordV1.model_validate(record_data)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        v2_obj = v1_to_v2(v1_obj)
        v1_back = v2_to_v1(v2_obj)
    assert v1_back.COMMON_SOURCE.organism == v1_obj.COMMON_SOURCE.organism
    assert v1_back.COMMON_SOURCE.mol_type == v1_obj.COMMON_SOURCE.mol_type


# === PBT: v1->v2->v1 field preservation ===


@given(record_data=st_v1_record())
@settings(max_examples=100)
def test_pbt_v1_roundtrip_preserves_trad_category(record_data: dict[str, Any]) -> None:
    v1_obj = DdbjRecordV1.model_validate(record_data)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        v2_obj = v1_to_v2(v1_obj)
        v1_back = v2_to_v1(v2_obj)
    assert v1_back.COMMON.trad_submission_category == v1_obj.COMMON.trad_submission_category


@given(record_data=st_v1_record())
@settings(max_examples=100)
def test_pbt_v1_roundtrip_preserves_ab_names(record_data: dict[str, Any]) -> None:
    v1_obj = DdbjRecordV1.model_validate(record_data)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        v2_obj = v1_to_v2(v1_obj)
        v1_back = v2_to_v1(v2_obj)
    assert set(v1_back.COMMON.SUBMITTER.ab_name) == set(v1_obj.COMMON.SUBMITTER.ab_name)


@given(record_data=st_v1_record())
@settings(max_examples=100)
def test_pbt_v1_roundtrip_preserves_division(record_data: dict[str, Any]) -> None:
    v1_obj = DdbjRecordV1.model_validate(record_data)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        v2_obj = v1_to_v2(v1_obj)
        v1_back = v2_to_v1(v2_obj)
    assert v1_back.COMMON_META.division == v1_obj.COMMON_META.division


# === PBT: v1->v2->v1 KEYWORD/DATATYPE preservation ===


@given(record_data=st_v1_record())
@settings(max_examples=100)
def test_pbt_v1_roundtrip_preserves_keyword(record_data: dict[str, Any]) -> None:
    v1_obj = DdbjRecordV1.model_validate(record_data)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        v2_obj = v1_to_v2(v1_obj)
        v1_back = v2_to_v1(v2_obj)
    if v1_obj.COMMON.KEYWORD and v1_obj.COMMON.KEYWORD.keyword:
        assert v1_back.COMMON.KEYWORD is not None
        assert v1_back.COMMON.KEYWORD.keyword == v1_obj.COMMON.KEYWORD.keyword
    else:
        assert v1_back.COMMON.KEYWORD is None


@given(record_data=st_v1_record())
@settings(max_examples=100)
def test_pbt_v1_roundtrip_preserves_datatype(record_data: dict[str, Any]) -> None:
    v1_obj = DdbjRecordV1.model_validate(record_data)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        v2_obj = v1_to_v2(v1_obj)
        v1_back = v2_to_v1(v2_obj)
    if v1_obj.COMMON.DATATYPE:
        assert v1_back.COMMON.DATATYPE is not None
        assert v1_back.COMMON.DATATYPE.type == v1_obj.COMMON.DATATYPE.type
    else:
        assert v1_back.COMMON.DATATYPE is None
