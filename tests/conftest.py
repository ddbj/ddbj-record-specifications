"""Test configuration for pytest."""

from pathlib import Path

import pytest


@pytest.fixture
def test_data_dir():
    """Return the path to test data directory."""
    return Path(__file__).parent / "data"


@pytest.fixture
def sample_v1_json():
    """Return sample v1 JSON data."""
    return {
        "submitter": {
            "contact_person": {
                "first_name": "Test",
                "last_name": "User",
                "email": "test@example.com"
            }
        },
        "sequences": [
            {
                "sequence_id": "test_seq_1",
                "sequence": "ATCGATCGATCG",
                "features": []
            }
        ]
    }


@pytest.fixture
def sample_v2_json():
    """Return sample v2 JSON data."""
    return {
        "submitter": {
            "contact_person": {
                "first_name": "Test",
                "last_name": "User",
                "email": "test@example.com"
            }
        },
        "sequences": [
            {
                "sequence_id": "test_seq_1",
                "sequence": "ATCGATCGATCG",
                "features": []
            }
        ]
    }
