import warnings
from typing import Any

import pytest

from ddbj_record.converter.v1_to_v2 import v1_to_v2
from ddbj_record.converter.v2_to_v1 import v2_to_v1
from ddbj_record.schema.v1 import DdbjRecord as DdbjRecordV1
from ddbj_record.schema.v2 import DdbjRecord as DdbjRecordV2

# === v1 -> v2 -> v1 roundtrip ===


def test_v1_to_v2_to_v1_preserves_organism(v1_to_v2_input: dict[str, Any]) -> None:
    v1_obj = DdbjRecordV1.model_validate(v1_to_v2_input)
    v2_obj = v1_to_v2(v1_obj)
    v1_back = v2_to_v1(v2_obj)
    assert v1_back.COMMON_SOURCE.organism == v1_obj.COMMON_SOURCE.organism


def test_v1_to_v2_to_v1_preserves_mol_type(v1_to_v2_input: dict[str, Any]) -> None:
    v1_obj = DdbjRecordV1.model_validate(v1_to_v2_input)
    v2_obj = v1_to_v2(v1_obj)
    v1_back = v2_to_v1(v2_obj)
    assert v1_back.COMMON_SOURCE.mol_type == v1_obj.COMMON_SOURCE.mol_type


def test_v1_to_v2_to_v1_preserves_entries_count(v1_to_v2_input: dict[str, Any]) -> None:
    v1_obj = DdbjRecordV1.model_validate(v1_to_v2_input)
    v2_obj = v1_to_v2(v1_obj)
    v1_back = v2_to_v1(v2_obj)
    assert len(v1_back.ENTRIES) == len(v1_obj.ENTRIES)


def test_v1_to_v2_to_v1_preserves_common_source(v1_to_v2_input: dict[str, Any]) -> None:
    """v1->v2->v1 roundtrip preserves COMMON_SOURCE fields."""
    v1_obj = DdbjRecordV1.model_validate(v1_to_v2_input)
    v2_obj = v1_to_v2(v1_obj)
    v1_back = v2_to_v1(v2_obj)
    original_cs = v1_obj.COMMON_SOURCE.model_dump(exclude_none=True)
    roundtrip_cs = v1_back.COMMON_SOURCE.model_dump(exclude_none=True)
    assert roundtrip_cs == original_cs


def test_v1_to_v2_to_v1_preserves_entry_ids(v1_to_v2_input: dict[str, Any]) -> None:
    """v1->v2->v1 roundtrip preserves entry IDs, types, and topologies."""
    v1_obj = DdbjRecordV1.model_validate(v1_to_v2_input)
    v2_obj = v1_to_v2(v1_obj)
    v1_back = v2_to_v1(v2_obj)
    for orig_entry, rt_entry in zip(v1_obj.ENTRIES, v1_back.ENTRIES, strict=True):
        assert rt_entry.id == orig_entry.id
        assert rt_entry.type == orig_entry.type
        assert rt_entry.topology == orig_entry.topology


# === v2 -> v1 -> v2 roundtrip ===


def test_v2_to_v1_to_v2_preserves_organism(v2_to_v1_input: dict[str, Any]) -> None:
    v2_obj = DdbjRecordV2.model_validate(v2_to_v1_input)
    v1_obj = v2_to_v1(v2_obj)
    v2_back = v1_to_v2(v1_obj)
    assert v2_back.sequences.common_source.organism == v2_obj.sequences.common_source.organism


def test_v2_to_v1_to_v2_preserves_entries_count(v2_to_v1_input: dict[str, Any]) -> None:
    v2_obj = DdbjRecordV2.model_validate(v2_to_v1_input)
    v1_obj = v2_to_v1(v2_obj)
    v2_back = v1_to_v2(v1_obj)
    assert len(v2_back.sequences.entries) == len(v2_obj.sequences.entries)


def test_v1_minimal_roundtrip_more_stable(v1_valid_minimal: dict[str, Any]) -> None:
    """Minimal data has fewer fields to lose, so roundtrip should be more stable."""
    v1_obj = DdbjRecordV1.model_validate(v1_valid_minimal)
    v2_obj = v1_to_v2(v1_obj)
    v1_back = v2_to_v1(v2_obj)
    assert v1_back.COMMON_SOURCE.organism == v1_obj.COMMON_SOURCE.organism
    assert v1_back.COMMON_SOURCE.mol_type == v1_obj.COMMON_SOURCE.mol_type
    assert v1_back.schema_version == "v1.0"


# === v1->v2->v1 field preservation across all v1 fixtures ===


@pytest.mark.parametrize(
    "fixture_name",
    ["v1_valid_minimal", "v1_valid_dfc_gnm", "v1_valid_wf_dfc_wgs"],
)
def test_v1_to_v2_to_v1_preserves_submitter_ab_names(fixture_name: str, request: pytest.FixtureRequest) -> None:
    v1_data: dict[str, Any] = request.getfixturevalue(fixture_name)
    v1_obj = DdbjRecordV1.model_validate(v1_data)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        v2_obj = v1_to_v2(v1_obj)
        v1_back = v2_to_v1(v2_obj)
    # v2→v1 filters out empty-string abbreviations, so compare non-empty only
    orig_non_empty = [n for n in v1_obj.COMMON.SUBMITTER.ab_name if n]
    rt_non_empty = [n for n in v1_back.COMMON.SUBMITTER.ab_name if n]
    assert rt_non_empty == orig_non_empty


@pytest.mark.parametrize(
    "fixture_name",
    ["v1_valid_minimal", "v1_valid_dfc_gnm", "v1_valid_wf_dfc_wgs"],
)
def test_v1_to_v2_to_v1_preserves_trad_category(fixture_name: str, request: pytest.FixtureRequest) -> None:
    v1_data: dict[str, Any] = request.getfixturevalue(fixture_name)
    v1_obj = DdbjRecordV1.model_validate(v1_data)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        v2_obj = v1_to_v2(v1_obj)
        v1_back = v2_to_v1(v2_obj)
    assert v1_back.COMMON.trad_submission_category == v1_obj.COMMON.trad_submission_category


@pytest.mark.parametrize(
    "fixture_name",
    ["v1_valid_minimal", "v1_valid_dfc_gnm", "v1_valid_wf_dfc_wgs"],
)
def test_v1_to_v2_to_v1_preserves_reference_titles(fixture_name: str, request: pytest.FixtureRequest) -> None:
    v1_data: dict[str, Any] = request.getfixturevalue(fixture_name)
    v1_obj = DdbjRecordV1.model_validate(v1_data)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        v2_obj = v1_to_v2(v1_obj)
        v1_back = v2_to_v1(v2_obj)
    for orig_ref, rt_ref in zip(v1_obj.COMMON.REFERENCE, v1_back.COMMON.REFERENCE, strict=True):
        assert rt_ref.title == orig_ref.title
        assert rt_ref.status == orig_ref.status
        assert rt_ref.year == orig_ref.year


@pytest.mark.parametrize(
    "fixture_name",
    ["v1_valid_minimal", "v1_valid_dfc_gnm", "v1_valid_wf_dfc_wgs"],
)
def test_v1_to_v2_to_v1_preserves_feature_count(fixture_name: str, request: pytest.FixtureRequest) -> None:
    v1_data: dict[str, Any] = request.getfixturevalue(fixture_name)
    v1_obj = DdbjRecordV1.model_validate(v1_data)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        v2_obj = v1_to_v2(v1_obj)
        v1_back = v2_to_v1(v2_obj)
    for orig_entry, rt_entry in zip(v1_obj.ENTRIES, v1_back.ENTRIES, strict=True):
        assert len(rt_entry.features) == len(orig_entry.features)


def test_v1_dfc_gnm_roundtrip_common_meta(v1_valid_dfc_gnm: dict[str, Any]) -> None:
    v1_obj = DdbjRecordV1.model_validate(v1_valid_dfc_gnm)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        v2_obj = v1_to_v2(v1_obj)
        v1_back = v2_to_v1(v2_obj)
    original_meta = v1_obj.COMMON_META.model_dump(exclude_none=True)
    roundtrip_meta = v1_back.COMMON_META.model_dump(exclude_none=True)
    assert roundtrip_meta == original_meta
