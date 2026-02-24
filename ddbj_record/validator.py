"""DDBJ Record Validator CLI.

Command-line interface for validating DDBJ record JSON files against schema specifications.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ValidationError, computed_field

from ddbj_record.schema import LATEST_VERSION, SCHEMA_VERSIONS, normalize_cli_version, normalize_schema_version
from ddbj_record.utils import resolve_record_model

# === Type Definitions for Validation ===


class ErrorDetail(BaseModel):
    type: str
    loc: list[str | int]
    msg: str
    severity: Literal["error", "warning"] = "error"
    context: dict[str, Any] | None = None
    stage: str | None = None


class ValidationSummary(BaseModel):
    error_count: int = 0
    warning_count: int = 0


class ValidationResult(BaseModel):
    valid: bool
    errors: list[ErrorDetail] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def submittable(self) -> bool:
        return not any(e.severity == "error" for e in self.errors)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def summary(self) -> ValidationSummary:
        return ValidationSummary(
            error_count=sum(1 for e in self.errors if e.severity == "error"),
            warning_count=sum(1 for e in self.errors if e.severity == "warning"),
        )


# === Pydantic loc normalization ===

_PYDANTIC_INTERNAL_RE = re.compile(r"^(function-after|function-wrap|function-before)\[.*\]$")


def _normalize_pydantic_loc(loc: tuple[str | int, ...] | list[str | int]) -> list[str | int]:
    return [
        seg for seg in loc if isinstance(seg, int) or (isinstance(seg, str) and not _PYDANTIC_INTERNAL_RE.match(seg))
    ]


# =======================================


class Args(BaseModel):
    """Command line arguments for the validator."""

    version: str
    input: Path
    no_insdc_validation: bool = False
    strict: bool = False
    fail_fast: bool = True


def parse_args(args: list[str] | None = None) -> Args:
    parser = argparse.ArgumentParser(
        description="DDBJ record - validates JSON file against specified schema version",
        epilog="Example: %(prog)s --version v1 --input sample_record.json",
    )

    parser.add_argument(
        "-v",
        "--version",
        type=str,
        default=LATEST_VERSION,
        help=f"Schema version to dump ({', '.join(SCHEMA_VERSIONS)})",
    )

    parser.add_argument("-i", "--input", type=Path, required=True, help="Path to JSON file to validate")
    parser.add_argument("--no-insdc-validation", action="store_true", help="Skip INSDC feature/qualifier validation")
    parser.add_argument("--strict", action="store_true", help="Treat unknown feature/qualifier keys as errors")
    parser.add_argument(
        "--no-fail-fast",
        action="store_true",
        help="Collect all errors from stage 3-4 instead of stopping at first failure",
    )

    if args is None:
        args = sys.argv[1:]

    parsed_args = parser.parse_args(args)
    normalized_version = normalize_cli_version(parsed_args.version)
    if normalized_version is None:
        parser.error(
            f"Invalid schema version: {parsed_args.version}. Supported versions are: {', '.join(SCHEMA_VERSIONS)}"
        )
    if not parsed_args.input.exists():
        parser.error(f"JSON file does not exist: {parsed_args.input}")

    return Args(
        version=normalized_version,
        input=parsed_args.input,
        no_insdc_validation=parsed_args.no_insdc_validation,
        strict=parsed_args.strict,
        fail_fast=not parsed_args.no_fail_fast,
    )


def validate_schema(json_data: dict[str, Any], schema_version: str) -> ValidationResult:
    record_model = resolve_record_model(schema_version)

    try:
        record_model.model_validate(json_data)
        return ValidationResult(valid=True)
    except ValidationError as e:
        errors: list[ErrorDetail] = []
        for err in e.errors():
            error_detail = ErrorDetail(
                type=err.get("type", "validation_error"),
                loc=_normalize_pydantic_loc(err.get("loc", ())),
                msg=err.get("msg", ""),
                stage="schema",
            )
            errors.append(error_detail)

        return ValidationResult(valid=False, errors=errors)


def _validate_referential_integrity(json_data: dict[str, Any], schema_version: str) -> list[ErrorDetail]:
    """Validate cross-field referential integrity constraints."""
    errors: list[ErrorDetail] = []

    if schema_version == "v2":
        # v2: sequences.entries[].id duplicate check
        sequences = json_data.get("sequences", {})
        entries = sequences.get("entries", [])
        entry_ids: set[str] = set()
        for i, entry in enumerate(entries):
            entry_id = entry.get("id", "")
            if entry_id in entry_ids:
                errors.append(
                    ErrorDetail(
                        type="duplicate_entry_id",
                        loc=["sequences", "entries", i, "id"],
                        msg=f"Duplicate entry id: '{entry_id}'",
                        stage="referential_integrity",
                    )
                )
            entry_ids.add(entry_id)

        # v2: features[].id duplicate check
        features = json_data.get("features", [])
        feature_ids: set[str] = set()
        for i, feature in enumerate(features):
            feat_id = feature.get("id", "")
            if feat_id in feature_ids:
                errors.append(
                    ErrorDetail(
                        type="duplicate_feature_id",
                        loc=["features", i, "id"],
                        msg=f"Duplicate feature id: '{feat_id}'",
                        stage="referential_integrity",
                    )
                )
            feature_ids.add(feat_id)

        # v2: feature.sequence_id reference check
        for i, feature in enumerate(features):
            seq_id = feature.get("sequence_id", "")
            if seq_id not in entry_ids:
                errors.append(
                    ErrorDetail(
                        type="invalid_sequence_id_reference",
                        loc=["features", i, "sequence_id"],
                        msg=f"sequence_id '{seq_id}' does not match any sequences.entries[].id",
                        stage="referential_integrity",
                    )
                )

        # v2: entry source feature existence check
        for i, entry in enumerate(entries):
            source_features = entry.get("source_features", [])
            if not source_features:
                entry_id = entry.get("id", "")
                errors.append(
                    ErrorDetail(
                        type="missing_source_feature",
                        loc=["sequences", "entries", i, "source_features"],
                        msg=f"Entry '{entry_id}' has no source feature",
                        stage="referential_integrity",
                    )
                )

        # v2: contact person info check
        submitters = json_data.get("submission", {}).get("submitters", [])
        if submitters:
            contact = submitters[0]
            if not contact.get("name"):
                errors.append(
                    ErrorDetail(
                        type="missing_contact_person_name",
                        loc=["submission", "submitters", 0, "name"],
                        msg="Contact person (submitters[0]) should have a name",
                        severity="warning",
                        stage="referential_integrity",
                    )
                )
            if not contact.get("email"):
                errors.append(
                    ErrorDetail(
                        type="missing_contact_person_email",
                        loc=["submission", "submitters", 0, "email"],
                        msg="Contact person (submitters[0]) should have an email",
                        severity="warning",
                        stage="referential_integrity",
                    )
                )

    elif schema_version == "v1":
        # v1: ENTRIES[].id duplicate check
        v1_entries = json_data.get("ENTRIES", [])
        entry_ids_v1: set[str] = set()
        for i, entry in enumerate(v1_entries):
            entry_id = entry.get("id", "")
            if entry_id in entry_ids_v1:
                errors.append(
                    ErrorDetail(
                        type="duplicate_entry_id",
                        loc=["ENTRIES", i, "id"],
                        msg=f"Duplicate entry id: '{entry_id}'",
                        stage="referential_integrity",
                    )
                )
            entry_ids_v1.add(entry_id)

        # v1: feature ID duplicate check across all entries + source feature existence
        feature_ids_v1: set[str] = set()
        for entry_idx, entry in enumerate(v1_entries):
            features = entry.get("features", [])
            has_source = False
            for feat_idx, feature in enumerate(features):
                feat_id = feature.get("id", "")
                if feat_id in feature_ids_v1:
                    errors.append(
                        ErrorDetail(
                            type="duplicate_feature_id",
                            loc=["ENTRIES", entry_idx, "features", feat_idx, "id"],
                            msg=f"Duplicate feature id: '{feat_id}'",
                            stage="referential_integrity",
                        )
                    )
                feature_ids_v1.add(feat_id)
                if feature.get("type") == "source":
                    has_source = True
            if not has_source:
                entry_id = entry.get("id", "")
                errors.append(
                    ErrorDetail(
                        type="missing_source_feature",
                        loc=["ENTRIES", entry_idx, "features"],
                        msg=f"Entry '{entry_id}' has no source feature",
                        stage="referential_integrity",
                    )
                )

    return errors


def _validate_schema_version_consistency(json_data: dict[str, Any], schema_version: str) -> list[ErrorDetail]:
    """Check that json_data's schema_version is consistent with the specified version."""
    raw_version = json_data.get("schema_version")
    if raw_version is None:
        return []

    normalized = normalize_schema_version(raw_version)
    if normalized is None:
        return [
            ErrorDetail(
                type="schema_version_mismatch",
                loc=["schema_version"],
                msg=f"schema_version '{raw_version}' is not recognized",
                stage="schema_version",
            )
        ]

    # Write back normalized value so Pydantic sees the canonical form
    json_data["schema_version"] = normalized

    prefix = f"{schema_version}."
    if not normalized.startswith(prefix):
        return [
            ErrorDetail(
                type="schema_version_mismatch",
                loc=["schema_version"],
                msg=f"schema_version '{raw_version}' is not compatible with specified version '{schema_version}'",
                stage="schema_version",
            )
        ]

    return []


def _validate_date_fields(json_data: dict[str, Any]) -> list[ErrorDetail]:
    """Validate that date fields contain actual valid dates.

    Pydantic's Field(pattern=...) checks the YYYY-MM-DD format, but does not
    verify that the date itself is valid (e.g., 2025-02-30 passes the pattern
    but is not a real date). This function catches such cases.
    """
    errors: list[ErrorDetail] = []

    submission = json_data.get("submission", {})
    hold_date = submission.get("hold_date")
    if hold_date is not None:
        try:
            datetime.date.fromisoformat(hold_date)
        except ValueError:
            errors.append(
                ErrorDetail(
                    type="invalid_date_value",
                    loc=["submission", "hold_date"],
                    msg=f"Invalid date value: '{hold_date}'",
                    stage="schema",
                )
            )

    references = submission.get("references", [])
    for i, ref in enumerate(references):
        date_published = ref.get("date_published")
        if date_published is not None:
            try:
                datetime.date.fromisoformat(date_published)
            except ValueError:
                errors.append(
                    ErrorDetail(
                        type="invalid_date_value",
                        loc=["submission", "references", i, "date_published"],
                        msg=f"Invalid date value: '{date_published}'",
                        stage="schema",
                    )
                )

    return errors


def validate_json_data(
    json_data: dict[str, Any],
    schema_version: str,
    *,
    no_insdc_validation: bool = False,
    strict: bool = False,
    fail_fast: bool = True,
) -> ValidationResult:
    # Stage 1: schema_version consistency check (always fail-fast: subsequent stages need valid version)
    version_errors = _validate_schema_version_consistency(json_data, schema_version)
    if version_errors:
        return ValidationResult(valid=False, errors=version_errors)

    # Stage 2: Validate against schema (always fail-fast: Pydantic model needed for later stages)
    validation_result = validate_schema(json_data, schema_version)
    if not validation_result.valid:
        return validation_result

    # Stage 2.5: Date field validity (format OK from Pydantic, check actual date)
    if schema_version == "v2":
        date_errors = _validate_date_fields(json_data)
        if date_errors:
            return ValidationResult(valid=False, errors=date_errors)

    # Stage 3-4: referential integrity + INSDC validation (respect fail_fast)
    all_errors: list[ErrorDetail] = []

    ref_errors = _validate_referential_integrity(json_data, schema_version)
    all_errors.extend(ref_errors)
    if fail_fast and any(e.severity == "error" for e in ref_errors):
        return ValidationResult(valid=False, errors=all_errors)

    if not no_insdc_validation:
        insdc_errors = _validate_insdc(json_data, schema_version, strict=strict)
        all_errors.extend(insdc_errors)

    if all_errors:
        has_errors = any(e.severity == "error" for e in all_errors)

        return ValidationResult(valid=not has_errors, errors=all_errors)

    return ValidationResult(valid=True)


def _validate_insdc(json_data: dict[str, Any], schema_version: str, *, strict: bool) -> list[ErrorDetail]:
    from ddbj_record.insdc.validator import validate_insdc_v1, validate_insdc_v2

    if schema_version == "v2":
        return validate_insdc_v2(json_data, strict=strict)
    if schema_version == "v1":
        return validate_insdc_v1(json_data, strict=strict)

    return []


def main() -> None:
    try:
        args = parse_args(sys.argv[1:])
    except SystemExit:
        raise
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        with args.input.open("r", encoding="utf-8") as f:
            json_data = json.load(f)
    except json.JSONDecodeError as e:
        result = ValidationResult(
            valid=False,
            errors=[ErrorDetail(type="json_parse_error", loc=[], msg=str(e), stage="schema")],
        )
        print(result.model_dump_json(indent=2))
        sys.exit(1)

    try:
        validation_result = validate_json_data(
            json_data,
            args.version,
            no_insdc_validation=args.no_insdc_validation,
            strict=args.strict,
            fail_fast=args.fail_fast,
        )
        print(validation_result.model_dump_json(indent=2))
        if not validation_result.valid:
            sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
