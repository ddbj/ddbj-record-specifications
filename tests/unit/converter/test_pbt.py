import warnings
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from ddbj_record.converter.v1_to_v2 import _normalize_abbr, _qualifier_value_to_str, v1_to_v2
from ddbj_record.converter.v2_to_v1 import _qualifier_value_to_union, v2_to_v1
from ddbj_record.converter.v2_to_v3 import v2_to_v3
from ddbj_record.schema.v1 import DdbjRecord as DdbjRecordV1
from ddbj_record.schema.v2 import DdbjRecord as DdbjRecordV2
from ddbj_record.schema.v3 import DdbjRecord as DdbjRecordV3

# === strategies ===

st_organism = st.text(min_size=1, max_size=80).filter(lambda s: s.strip() != "")
st_mol_type = st.sampled_from(["genomic DNA", "genomic RNA", "mRNA", "tRNA", "rRNA", "other DNA", "other RNA"])
st_trad_category = st.sampled_from(["WGS", "GNM"])
st_entry_type = st.sampled_from(["chromosome", "plasmid", "unplaced", "other"])
st_topology = st.sampled_from(["circular", "linear"])
st_abbr_name = st.from_regex(r"[A-Z][a-z]{1,10},[A-Z]\.", fullmatch=True)
st_keywords = st.one_of(st.none(), st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=5))
st_datatype = st.one_of(st.none(), st.text(min_size=1, max_size=20))
st_hold_date = st.one_of(st.none(), st.dates())


@st.composite
def st_v1_record(draw: st.DrawFn) -> dict[str, Any]:
    organism = draw(st_organism)
    mol_type = draw(st_mol_type)
    category = draw(st_trad_category)
    ab_name = draw(st_abbr_name)
    keywords = draw(st_keywords)
    datatype = draw(st_datatype)
    hold_date = draw(st_hold_date)

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
    if hold_date is not None:
        common["DATE"] = {"hold_date": f"{hold_date.year:04d}{hold_date.month:02d}{hold_date.day:02d}"}

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
    hold_date = draw(st_hold_date)

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
    if hold_date is not None:
        submission["hold_date"] = hold_date.isoformat()

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


st_entry_id = st.from_regex(r"[a-zA-Z0-9_.\-]{1,32}", fullmatch=True)
st_qualifier_name = st.sampled_from(["plasmid", "submitter_seqid", "note", "isolate", "environmental_sample"])
st_qualifier_values = st.lists(
    st.one_of(st.booleans(), st.text(min_size=1, max_size=20).filter(lambda s: s not in ("true", "false"))),
    min_size=1,
    max_size=3,
)


@st.composite
def st_v1_source_qualifiers(draw: st.DrawFn) -> dict[str, list[str | bool]]:
    """entry の source feature の qualifiers。organism / mol_type / ff_definition はそれぞれ有ったり無かったりする。"""
    qualifiers: dict[str, list[str | bool]] = {}
    for name in draw(st.lists(st_qualifier_name, unique=True, max_size=3)):
        qualifiers[name] = draw(st_qualifier_values)
    if draw(st.booleans()):
        qualifiers["organism"] = [draw(st_organism)]
    if draw(st.booleans()):
        qualifiers["mol_type"] = [draw(st_mol_type)]
    if draw(st.booleans()):
        qualifiers["ff_definition"] = ["@@[organism]@@ DNA"]
    return qualifiers


@st.composite
def st_v1_record_with_entries(draw: st.DrawFn) -> dict[str, Any]:
    record = draw(st_v1_record())
    entry_ids = draw(st.lists(st_entry_id, unique=True, min_size=1, max_size=3))
    record["ENTRIES"] = [
        {
            "id": entry_id,
            "name": entry_id,
            "type": draw(st_entry_type),
            "topology": draw(st_topology),
            "sequence": "atgc",
            "features": [
                {"id": f"sf_{i}", "type": "source", "location": "1..4", "qualifiers": draw(st_v1_source_qualifiers())}
            ],
        }
        for i, entry_id in enumerate(entry_ids)
    ]
    return record


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


# === PBT: entry の source feature の qualifier が v1 -> v2 で残る ===


@given(record_data=st_v1_record_with_entries())
@settings(max_examples=100)
def test_pbt_v1_to_v2_keeps_every_entry_source_qualifier(record_data: dict[str, Any]) -> None:
    """ff_definition 以外の qualifier が 1 つでもあれば Source ができ、全ての qualifier が同じ値で残る。

    organism / mol_type は Source のフィールドに、無ければ COMMON_SOURCE の値が入る。
    """
    v1_obj = DdbjRecordV1.model_validate(record_data)
    v2_obj = v1_to_v2(v1_obj)
    for v1_entry, v2_entry in zip(v1_obj.ENTRIES, v2_obj.sequences.entries, strict=True):
        v1_sf = v1_entry.features[0]
        v2_source = v2_entry.source_features[0].source
        if all(key == "ff_definition" for key in v1_sf.qualifiers):
            assert v2_source is None
            continue
        assert v2_source is not None
        expected_organism = v1_sf.qualifiers.get("organism", [v1_obj.COMMON_SOURCE.organism])[0]
        expected_mol_type = v1_sf.qualifiers.get("mol_type", [v1_obj.COMMON_SOURCE.mol_type])[0]
        assert v2_source.organism == expected_organism
        assert v2_source.mol_type == expected_mol_type
        for key, values in v1_sf.qualifiers.items():
            if key in ("organism", "mol_type", "ff_definition"):
                assert key not in v2_source.qualifiers
                continue
            assert [q.value for q in v2_source.qualifiers[key]] == [_qualifier_value_to_str(v) for v in values]


@given(record_data=st_v1_record_with_entries())
@settings(max_examples=100)
def test_pbt_v1_roundtrip_restores_entry_source_qualifiers(record_data: dict[str, Any]) -> None:
    """v1 -> v2 -> v1 で、entry の source feature の qualifier が元に戻る。

    例外は、COMMON_SOURCE と同じ organism / mol_type を entry に重ねて書いていたもので、これは v2 -> v1 で
    書かないので消える。
    """
    v1_obj = DdbjRecordV1.model_validate(record_data)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        v1_back = v2_to_v1(v1_to_v2(v1_obj))
    common = {"organism": [v1_obj.COMMON_SOURCE.organism], "mol_type": [v1_obj.COMMON_SOURCE.mol_type]}
    for v1_entry, rt_entry in zip(v1_obj.ENTRIES, v1_back.ENTRIES, strict=True):
        orig = v1_entry.features[0].qualifiers
        expected = {key: values for key, values in orig.items() if common.get(key) != values}
        assert rt_entry.features[0].qualifiers == expected


# === PBT: v2 -> v3 ===

st_v2_qualifier_value = st.one_of(st.just("true"), st.text(min_size=1, max_size=20).filter(lambda s: s != "true"))
st_v2_qualifiers = st.dictionaries(
    keys=st.sampled_from(["product", "note", "pseudo", "gene", "plasmid"]),
    values=st.lists(st.builds(dict, value=st_v2_qualifier_value), min_size=1, max_size=2),
    max_size=3,
)
st_comment_lines = st.lists(st.lists(st.text(max_size=10), max_size=2), max_size=2)
st_year = st.sampled_from(["", "2023", "2024"])


@st.composite
def st_v2_reference(draw: st.DrawFn) -> dict[str, Any]:
    reference: dict[str, Any] = {
        "title": draw(st.text(min_size=1, max_size=20)),
        "authors": [{"abbreviation": draw(st_abbr_name)}],
        "status": draw(st.sampled_from(["unpublished", "in-press", "published"])),
        "year": draw(st_year),
    }
    if draw(st.booleans()):
        reference["date_published"] = draw(st.dates()).isoformat()
    return reference


@st.composite
def st_v2_record_rich(draw: st.DrawFn) -> dict[str, Any]:
    """entries / features / qualifiers / comments / references を持つ v2 の record。"""
    record = draw(st_v2_record())
    record["submission"]["references"] = draw(st.lists(st_v2_reference(), max_size=2))
    record["submission"]["comments"] = draw(st_comment_lines)
    record["submission"]["division"] = draw(st.one_of(st.none(), st.sampled_from(["BCT", "UNK"])))
    record["sequences"]["common_source"]["qualifiers"] = draw(st_v2_qualifiers)

    entries: list[dict[str, Any]] = []
    features: list[dict[str, Any]] = []
    for i, entry_id in enumerate(draw(st.lists(st_entry_id, unique=True, max_size=3))):
        source_feature: dict[str, Any] = {"id": f"sf_{i}", "location": "1..4"}
        if draw(st.booleans()):
            source_feature["source"] = {
                "organism": draw(st_organism),
                "mol_type": draw(st_mol_type),
                "qualifiers": draw(st_v2_qualifiers),
            }
        entry: dict[str, Any] = {
            "id": entry_id,
            "name": entry_id,
            "type": draw(st_entry_type),
            "topology": draw(st_topology),
            "source_features": [source_feature],
        }
        if draw(st.booleans()):
            entry["comments"] = draw(st_comment_lines)
        entries.append(entry)
        features.extend(
            {
                "id": f"f_{i}_{j}",
                "type": "CDS",
                "location": "1..4",
                "sequence_id": entry_id,
                "qualifiers": draw(st_v2_qualifiers),
            }
            for j in range(draw(st.integers(min_value=0, max_value=2)))
        )
    record["sequences"]["entries"] = entries
    record["features"] = features
    return record


def _v3_qualifier_values(qualifiers: dict[str, list[Any]] | None) -> dict[str, list[tuple[str | None, str | None]]]:
    return {name: [(q.alias, q.value) for q in values] for name, values in (qualifiers or {}).items()}


def _expected_v3_qualifier_values(qualifiers: dict[str, list[Any]]) -> dict[str, list[tuple[str | None, str | None]]]:
    return {
        name: [(q.id, None if q.value == "true" else q.value) for q in values] for name, values in qualifiers.items()
    }


@given(record_data=st_v2_record_rich())
@settings(max_examples=100)
def test_pbt_v2_to_v3_produces_valid_v3_that_reads_back_unchanged(record_data: dict[str, Any]) -> None:
    v3_obj = v2_to_v3(DdbjRecordV2.model_validate(record_data))
    dumped = v3_obj.model_dump(exclude_none=True, by_alias=True)
    assert dumped["schema_version"] == "v3"
    assert DdbjRecordV3.model_validate(dumped).model_dump(exclude_none=True, by_alias=True) == dumped


@given(record_data=st_v2_record_rich())
@settings(max_examples=100)
def test_pbt_v2_to_v3_keeps_entries_and_features(record_data: dict[str, Any]) -> None:
    v2_obj = DdbjRecordV2.model_validate(record_data)
    v3_obj = v2_to_v3(v2_obj)
    assert v3_obj.sequences is not None
    v3_entries = v3_obj.sequences.entries or []
    assert [e.alias for e in v3_entries] == [e.id for e in v2_obj.sequences.entries]
    assert [(f.alias, f.sequence_id) for f in v3_obj.features or []] == [(f.id, f.sequence_id) for f in v2_obj.features]
    for v2_entry, v3_entry in zip(v2_obj.sequences.entries, v3_entries, strict=True):
        assert v3_entry.division == v2_obj.submission.division
        expected_comments = ["\n".join(lines) for lines in v2_entry.comments or [] if lines] or None
        assert v3_entry.comments == expected_comments


@given(record_data=st_v2_record_rich())
@settings(max_examples=100)
def test_pbt_v2_to_v3_keeps_every_qualifier_and_drops_only_true(record_data: dict[str, Any]) -> None:
    """全ての qualifier が同じ名前・同じ順序で残り、"true" だけが value の無い qualifier になる。"""
    v2_obj = DdbjRecordV2.model_validate(record_data)
    v3_obj = v2_to_v3(v2_obj)
    assert v3_obj.sequences is not None
    assert v3_obj.sequences.common_source is not None
    assert _v3_qualifier_values(v3_obj.sequences.common_source.qualifiers) == _expected_v3_qualifier_values(
        v2_obj.sequences.common_source.qualifiers
    )
    for v2_feature, v3_feature in zip(v2_obj.features, v3_obj.features or [], strict=True):
        assert _v3_qualifier_values(v3_feature.qualifiers) == _expected_v3_qualifier_values(v2_feature.qualifiers)
    for v2_entry, v3_entry in zip(v2_obj.sequences.entries, v3_obj.sequences.entries or [], strict=True):
        v2_source = v2_entry.source_features[0].source
        assert v3_entry.source_features is not None
        v3_source = v3_entry.source_features[0].source
        if v2_source is None:
            assert v3_source is None
            continue
        assert v3_source is not None
        assert v3_source.organism is not None
        assert v3_source.organism.name == v2_source.organism
        assert _v3_qualifier_values(v3_source.qualifiers) == _expected_v3_qualifier_values(v2_source.qualifiers)


@given(record_data=st_v2_record_rich())
@settings(max_examples=100)
def test_pbt_v2_to_v3_keeps_submission_values(record_data: dict[str, Any]) -> None:
    v2_obj = DdbjRecordV2.model_validate(record_data)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        v3_obj = v2_to_v3(v2_obj)
    assert v3_obj.sequences is not None
    assert v3_obj.sequences.keywords == (v2_obj.submission.keywords or None)
    assert v3_obj.sequences.common_source is not None
    assert v3_obj.sequences.common_source.organism is not None
    assert v3_obj.sequences.common_source.organism.name == v2_obj.sequences.common_source.organism
    assert v3_obj.sequences.common_source.mol_type == v2_obj.sequences.common_source.mol_type
    expected_comments = ["\n".join(lines) for lines in v2_obj.submission.comments if lines] or None
    assert v3_obj.submission is not None
    assert v3_obj.submission.comments == expected_comments
    assert v3_obj.submission.hold_date == v2_obj.submission.hold_date


@given(record_data=st_v2_record_rich())
@settings(max_examples=100)
def test_pbt_v2_to_v3_publications_take_date_published_or_year(record_data: dict[str, Any]) -> None:
    v2_obj = DdbjRecordV2.model_validate(record_data)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        v3_obj = v2_to_v3(v2_obj)
    if not v2_obj.submission.references:
        assert v3_obj.projects is None
        return
    assert v3_obj.projects is not None
    publications = v3_obj.projects[0].publications or []
    assert len(publications) == len(v2_obj.submission.references)
    for reference, publication in zip(v2_obj.submission.references, publications, strict=True):
        assert publication.title == reference.title
        assert publication.status == reference.status
        assert publication.date == (reference.date_published or reference.year or None)


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


# === PBT: hold_date format preservation ===


@given(record_data=st_v1_record())
@settings(max_examples=100)
def test_pbt_v1_roundtrip_preserves_hold_date(record_data: dict[str, Any]) -> None:
    """The v1 side carries the MSS DATE format, so a detour through v2 must return the same digits."""
    v1_obj = DdbjRecordV1.model_validate(record_data)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        v2_obj = v1_to_v2(v1_obj)
        v1_back = v2_to_v1(v2_obj)
    if v1_obj.COMMON.DATE:
        assert v1_back.COMMON.DATE is not None
        assert v1_back.COMMON.DATE.hold_date == v1_obj.COMMON.DATE.hold_date
    else:
        assert v1_back.COMMON.DATE is None


@given(record_data=st_v2_record())
@settings(max_examples=100)
def test_pbt_v2_roundtrip_preserves_hold_date(record_data: dict[str, Any]) -> None:
    v2_obj = DdbjRecordV2.model_validate(record_data)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        v1_obj = v2_to_v1(v2_obj)
        v2_back = v1_to_v2(v1_obj)
    assert v2_back.submission.hold_date == v2_obj.submission.hold_date
