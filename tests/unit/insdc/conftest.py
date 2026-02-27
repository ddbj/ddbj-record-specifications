"""Shared test fixtures and helpers for INSDC validation tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

MakeDataFn = Callable[[list[dict[str, Any]]], dict[str, Any]]


def _make_v2_data_raw(features: list[dict[str, Any]]) -> dict[str, Any]:
    """Raw helper for v2 data (usable from Hypothesis tests)."""
    return {
        "sequences": {
            "common_source": {"organism": "Test", "mol_type": "genomic DNA"},
            "entries": [
                {
                    "id": "seq1",
                    "source_features": [{"id": "sf1", "location": "1..100"}],
                }
            ],
        },
        "features": features,
    }


def _make_v1_data_raw(features: list[dict[str, Any]]) -> dict[str, Any]:
    """Raw helper for v1 data (usable from Hypothesis tests)."""
    return {
        "ENTRIES": [
            {
                "id": "entry1",
                "features": [
                    {
                        "id": "sf1",
                        "type": "source",
                        "qualifiers": {
                            "organism": ["Test"],
                            "mol_type": ["genomic DNA"],
                        },
                    },
                    *features,
                ],
            }
        ]
    }


@pytest.fixture
def make_v2_data() -> MakeDataFn:
    """Create minimal v2 JSON data with the given features."""
    return _make_v2_data_raw


@pytest.fixture
def make_v1_data() -> MakeDataFn:
    """Create minimal v1 JSON data with the given non-source features."""
    return _make_v1_data_raw
