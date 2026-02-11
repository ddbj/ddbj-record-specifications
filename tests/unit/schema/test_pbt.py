from hypothesis import given, settings
from hypothesis import strategies as st

from ddbj_record.schema import LEGACY_SCHEMA_VERSION_MAP
from ddbj_record.schema.v2 import (
    DdbjRecord,
    Qualifier,
)

# === strategies ===

st_organism = st.text(min_size=1, max_size=100).filter(lambda s: s.strip() != "")
st_mol_type = st.sampled_from(["genomic DNA", "genomic RNA", "mRNA", "tRNA", "rRNA", "other DNA", "other RNA"])
st_entry_type = st.sampled_from(["chromosome", "plasmid", "unplaced", "other"])
st_topology = st.sampled_from(["circular", "linear"])


@st.composite
def st_v2_minimal_record(draw: st.DrawFn) -> dict:
    organism = draw(st_organism)
    mol_type = draw(st_mol_type)

    return {
        "schema_version": "v2.0",
        "provenance": {},
        "submission": {},
        "sequences": {
            "common_source": {
                "organism": organism,
                "mol_type": mol_type,
            },
        },
    }


@st.composite
def st_v2_record_with_entry(draw: st.DrawFn) -> dict:
    organism = draw(st_organism)
    mol_type = draw(st_mol_type)
    entry_type = draw(st_entry_type)
    topology = draw(st_topology)
    entry_id = draw(st.from_regex(r"[a-zA-Z0-9_.\-]{1,32}", fullmatch=True))

    return {
        "schema_version": "v2.0",
        "provenance": {},
        "submission": {},
        "sequences": {
            "common_source": {
                "organism": organism,
                "mol_type": mol_type,
            },
            "entries": [
                {
                    "id": entry_id,
                    "name": entry_id,
                    "type": entry_type,
                    "topology": topology,
                }
            ],
        },
    }


# === PBT tests ===


@given(record_data=st_v2_minimal_record())
@settings(max_examples=100)
def test_pbt_v2_minimal_record_validates(record_data: dict) -> None:
    record = DdbjRecord.model_validate(record_data)
    assert record.schema_version == "v2.0"


@given(record_data=st_v2_record_with_entry())
@settings(max_examples=100)
def test_pbt_v2_record_with_entry_validates(record_data: dict) -> None:
    record = DdbjRecord.model_validate(record_data)
    assert len(record.sequences.entries) == 1


@given(record_data=st_v2_minimal_record())
@settings(max_examples=100)
def test_pbt_schema_version_normalization_idempotent(record_data: dict) -> None:
    record1 = DdbjRecord.model_validate(record_data)
    dumped = record1.model_dump(exclude_none=True, by_alias=True)
    record2 = DdbjRecord.model_validate(dumped)
    assert record1.schema_version == record2.schema_version


@given(record_data=st_v2_minimal_record())
@settings(max_examples=100)
def test_pbt_model_dump_validate_roundtrip(record_data: dict) -> None:
    record1 = DdbjRecord.model_validate(record_data)
    dumped = record1.model_dump(exclude_none=True, by_alias=True)
    record2 = DdbjRecord.model_validate(dumped)
    assert record1.sequences.common_source.organism == record2.sequences.common_source.organism
    assert record1.sequences.common_source.mol_type == record2.sequences.common_source.mol_type


@given(legacy_key=st.sampled_from(list(LEGACY_SCHEMA_VERSION_MAP.keys())))
def test_pbt_legacy_version_map_values_are_versioned(legacy_key: str) -> None:
    value = LEGACY_SCHEMA_VERSION_MAP[legacy_key]
    assert value.startswith("v")
    assert "." in value


@given(value=st.text(min_size=1, max_size=50))
@settings(max_examples=100)
def test_pbt_qualifier_value_always_str(value: str) -> None:
    q = Qualifier(value=value)
    assert isinstance(q.value, str)
    assert q.value == value
