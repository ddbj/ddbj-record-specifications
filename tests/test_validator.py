"""Tests for the validator module."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from ddbj_record.validator import (Args, SchemaVersion, main, parse_args,
                                   validate_json_data)


class TestSchemaVersion:
    """Test SchemaVersion enum."""

    def test_schema_version_values(self):
        """Test that schema version values are correct."""
        assert SchemaVersion.V1.value == "v1"
        assert SchemaVersion.V2.value == "v2"


class TestArgs:
    """Test Args model."""

    def test_args_creation(self):
        """Test creating Args with valid data."""
        args = Args(
            schema_version=SchemaVersion.V1,
            json_file=Path("test.json")
        )
        assert args.schema_version == SchemaVersion.V1
        assert args.json_file == Path("test.json")


class TestParseArgs:
    """Test parse_args function."""

    def test_parse_args_valid(self):
        """Test parsing valid arguments."""
        test_args = ["v1", "--json", "test.json"]
        args = parse_args(test_args)

        assert args.schema_version == SchemaVersion.V1
        assert args.json_file == Path("test.json")

    def test_parse_args_v2(self):
        """Test parsing v2 schema argument."""
        test_args = ["v2", "--json", "test.json"]
        args = parse_args(test_args)

        assert args.schema_version == SchemaVersion.V2
        assert args.json_file == Path("test.json")

    def test_parse_args_missing_json(self):
        """Test parsing arguments without --json flag."""
        test_args = ["v1"]

        with pytest.raises(SystemExit):
            parse_args(test_args)

    def test_parse_args_invalid_schema(self):
        """Test parsing with invalid schema version."""
        test_args = ["v3", "--json", "test.json"]

        with pytest.raises(SystemExit):
            parse_args(test_args)


class TestValidateJsonData:
    """Test validate_json_data function."""

    @patch('ddbj_record_validator.validator.DdbjRecordV1')
    def test_validate_v1_success(self, mock_v1):
        """Test successful v1 validation."""
        mock_v1.return_value = None
        test_data = {"test": "data"}

        # Should not raise an exception
        validate_json_data(test_data, SchemaVersion.V1)

        mock_v1.assert_called_once_with(**test_data)

    @patch('ddbj_record_validator.validator.DdbjRecordV2')
    def test_validate_v2_success(self, mock_v2):
        """Test successful v2 validation."""
        mock_v2.return_value = None
        test_data = {"test": "data"}

        # Should not raise an exception
        validate_json_data(test_data, SchemaVersion.V2)

        mock_v2.assert_called_once_with(**test_data)

    @patch('ddbj_record_validator.validator.DdbjRecordV1')
    def test_validate_v1_failure(self, mock_v1):
        """Test v1 validation failure."""
        mock_v1.side_effect = ValidationError("test error", model=None)
        test_data = {"test": "data"}

        with pytest.raises(SystemExit):
            validate_json_data(test_data, SchemaVersion.V1)


class TestMain:
    """Test main function."""

    @patch('ddbj_record_validator.validator.parse_args')
    @patch('ddbj_record_validator.validator.validate_json_data')
    def test_main_success(self, mock_validate, mock_parse_args, tmp_path):
        """Test successful main execution."""
        # Create a temporary JSON file
        test_file = tmp_path / "test.json"
        test_data = {"test": "data"}
        test_file.write_text(json.dumps(test_data))

        # Mock parse_args to return our test args
        mock_parse_args.return_value = Args(
            schema_version=SchemaVersion.V1,
            json_file=test_file
        )

        # Mock validate_json_data to succeed
        mock_validate.return_value = None

        # Should not raise an exception
        main()

        mock_validate.assert_called_once_with(test_data, SchemaVersion.V1)

    @patch('ddbj_record_validator.validator.parse_args')
    def test_main_file_not_found(self, mock_parse_args):
        """Test main with non-existent file."""
        mock_parse_args.return_value = Args(
            schema_version=SchemaVersion.V1,
            json_file=Path("nonexistent.json")
        )

        with pytest.raises(SystemExit):
            main()

    @patch('ddbj_record_validator.validator.parse_args')
    def test_main_invalid_json(self, mock_parse_args, tmp_path):
        """Test main with invalid JSON."""
        # Create a file with invalid JSON
        test_file = tmp_path / "invalid.json"
        test_file.write_text("invalid json content")

        mock_parse_args.return_value = Args(
            schema_version=SchemaVersion.V1,
            json_file=test_file
        )

        with pytest.raises(SystemExit):
            main()

    @patch('ddbj_record_validator.validator.parse_args')
    def test_main_keyboard_interrupt(self, mock_parse_args):
        """Test main handling KeyboardInterrupt."""
        mock_parse_args.side_effect = KeyboardInterrupt()

        with pytest.raises(SystemExit):
            main()
