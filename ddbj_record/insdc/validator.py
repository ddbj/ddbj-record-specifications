"""INSDC feature/qualifier validation logic."""

from __future__ import annotations

import re
from typing import Any

from ddbj_record.insdc import load_insdc_definition
from ddbj_record.insdc.models import CrossConstraint, FeatureDefinition, InsdcDefinition
from ddbj_record.validator import ErrorDetail

# === Phase 1: Feature Key Validation ===


def _validate_feature_key(
    definition: InsdcDefinition,
    feature_type: str,
    loc_prefix: list[str | int],
    *,
    strict: bool,
) -> list[ErrorDetail]:
    if feature_type in definition.features:
        return []

    severity = "error" if strict else "warning"

    return [
        ErrorDetail(
            type="unknown_feature_key",
            loc=[*loc_prefix, "type"],
            msg=f"Unknown feature key: '{feature_type}'",
            severity=severity,
        )
    ]


# === Phase 2: Qualifier Key Validation ===


def _validate_qualifier_keys(
    definition: InsdcDefinition,
    feature_def: FeatureDefinition,
    feature_type: str,
    qualifiers: dict[str, Any],
    loc_prefix: list[str | int],
    *,
    strict: bool,
    skip_mandatory_as_warning: bool = False,
    already_satisfied: set[str] | None = None,
) -> list[ErrorDetail]:
    errors: list[ErrorDetail] = []
    satisfied = already_satisfied or set()

    # Check for unknown qualifier keys
    for qual_name in qualifiers:
        if qual_name not in feature_def.qualifiers:
            severity = "error" if strict else "warning"
            errors.append(
                ErrorDetail(
                    type="unknown_qualifier_key",
                    loc=[*loc_prefix, "qualifiers", qual_name],
                    msg=f"Qualifier '/{qual_name}' is not valid for feature '{feature_type}'",
                    severity=severity,
                )
            )

    # Check for missing mandatory qualifiers
    for qual_name, requirement in feature_def.qualifiers.items():
        if requirement == "mandatory" and qual_name not in qualifiers and qual_name not in satisfied:
            severity = "warning" if skip_mandatory_as_warning else "error"
            errors.append(
                ErrorDetail(
                    type="missing_mandatory_qualifier",
                    loc=[*loc_prefix, "qualifiers"],
                    msg=f"Mandatory qualifier '/{qual_name}' is missing for feature '{feature_type}'",
                    severity=severity,
                )
            )

    # Check for deprecated qualifiers
    for qual_name in qualifiers:
        if qual_name in definition.qualifiers:
            qual_def = definition.qualifiers[qual_name]
            if qual_def.deprecated is not None:
                errors.append(
                    ErrorDetail(
                        type="deprecated_qualifier",
                        loc=[*loc_prefix, "qualifiers", qual_name],
                        msg=qual_def.deprecated.message,
                        severity="warning",
                    )
                )

    return errors


# === Phase 3: Value Format Validation ===


def _validate_qualifier_values(
    definition: InsdcDefinition,
    qualifiers: dict[str, Any],
    loc_prefix: list[str | int],
    *,
    allowed_qualifiers: set[str] | None = None,
) -> list[ErrorDetail]:
    errors: list[ErrorDetail] = []

    for qual_name, qual_values in qualifiers.items():
        if qual_name not in definition.qualifiers:
            continue
        if allowed_qualifiers is not None and qual_name not in allowed_qualifiers:
            continue

        qual_def = definition.qualifiers[qual_name]

        if not isinstance(qual_values, list):
            continue

        for idx, qual_entry in enumerate(qual_values):
            value = _extract_qualifier_value(qual_entry)
            if value is None:
                continue

            loc = [*loc_prefix, "qualifiers", qual_name, idx, "value"]

            if qual_def.value_format == "controlled_vocabulary" and qual_def.controlled_vocabulary is not None:
                if value not in qual_def.controlled_vocabulary:
                    errors.append(
                        ErrorDetail(
                            type="invalid_qualifier_value",
                            loc=loc,
                            msg=f"Value '{value}' is not in the controlled vocabulary for '/{qual_name}'",
                            severity="error",
                        )
                    )

            elif qual_def.value_format == "none" and value != "true":
                errors.append(
                    ErrorDetail(
                        type="invalid_qualifier_value",
                        loc=loc,
                        msg=f"Boolean qualifier '/{qual_name}' must have value 'true', got '{value}'",
                        severity="error",
                    )
                )

            if qual_def.regex is not None and not re.search(qual_def.regex, value):
                errors.append(
                    ErrorDetail(
                        type="invalid_qualifier_value",
                        loc=loc,
                        msg=f"Value '{value}' does not match expected pattern for '/{qual_name}'",
                        severity="error",
                    )
                )

    return errors


def _extract_qualifier_value(qual_entry: Any) -> str | None:
    """Extract value string from a qualifier entry (v2 Qualifier object or v1 raw value)."""
    if isinstance(qual_entry, dict):
        return qual_entry.get("value")
    if isinstance(qual_entry, str):
        return qual_entry
    if isinstance(qual_entry, bool):
        return "true" if qual_entry else "false"

    return None


# === Phase 3: Cross-Constraint Validation ===


def _validate_cross_constraints(
    definition: InsdcDefinition,
    qualifiers: dict[str, Any],
    feature_type: str,
    loc_prefix: list[str | int],
) -> list[ErrorDetail]:
    errors: list[ErrorDetail] = []
    qual_keys = set(qualifiers.keys())

    for constraint in definition.cross_constraints:
        errors.extend(_check_single_constraint(constraint, qual_keys, qualifiers, feature_type, loc_prefix))

    return errors


def _check_single_constraint(
    constraint: CrossConstraint,
    qual_keys: set[str],
    qualifiers: dict[str, Any],
    feature_type: str,
    loc_prefix: list[str | int],
) -> list[ErrorDetail]:
    if constraint.type == "mutual_exclusion":
        return _check_mutual_exclusion(constraint, qual_keys, loc_prefix)
    if constraint.type == "dependency":
        return _check_dependency(constraint, qual_keys, loc_prefix)
    if constraint.type == "exclusion":
        return _check_mutual_exclusion(constraint, qual_keys, loc_prefix)

    return _check_conditional_mandatory(constraint, qual_keys, qualifiers, feature_type, loc_prefix)


def _check_mutual_exclusion(
    constraint: CrossConstraint,
    qual_keys: set[str],
    loc_prefix: list[str | int],
) -> list[ErrorDetail]:
    if constraint.qualifiers is None:
        return []

    present = [q for q in constraint.qualifiers if q in qual_keys]
    if len(present) > 1:
        return [
            ErrorDetail(
                type="constraint_violation",
                loc=[*loc_prefix, "qualifiers"],
                msg=constraint.message,
                severity="error",
            )
        ]

    return []


def _check_dependency(
    constraint: CrossConstraint,
    qual_keys: set[str],
    loc_prefix: list[str | int],
) -> list[ErrorDetail]:
    if constraint.qualifier is None or constraint.requires is None:
        return []

    if constraint.qualifier not in qual_keys:
        return []

    required = constraint.requires if isinstance(constraint.requires, list) else [constraint.requires]
    if any(r in qual_keys for r in required):
        return []

    return [
        ErrorDetail(
            type="constraint_violation",
            loc=[*loc_prefix, "qualifiers", constraint.qualifier],
            msg=constraint.message,
            severity="error",
        )
    ]



def _check_conditional_mandatory(
    constraint: CrossConstraint,
    qual_keys: set[str],
    qualifiers: dict[str, Any],
    feature_type: str,
    loc_prefix: list[str | int],
) -> list[ErrorDetail]:
    if constraint.feature is not None and constraint.feature != feature_type:
        return []
    if constraint.condition is None or constraint.then_mandatory is None:
        return []

    condition_met = _evaluate_condition(constraint.condition, qual_keys, qualifiers)
    if not condition_met:
        return []

    return [
        ErrorDetail(
            type="missing_mandatory_qualifier",
            loc=[*loc_prefix, "qualifiers"],
            msg=constraint.message,
            severity="error",
        )
        for qual_name in constraint.then_mandatory
        if qual_name not in qual_keys
    ]


def _evaluate_condition(
    condition: str,
    qual_keys: set[str],
    qualifiers: dict[str, Any],
) -> bool:
    """Evaluate a condition string.

    Supported formats:
    - "absent:qual1,qual2" -> True if ALL listed qualifiers are absent
    - "value:qual=val1,val2" -> True if qual's value is one of the listed values
    """
    if condition.startswith("absent:"):
        absent_quals = condition[len("absent:") :].split(",")

        return all(q not in qual_keys for q in absent_quals)

    if condition.startswith("value:"):
        rest = condition[len("value:") :]
        qual_name, values_str = rest.split("=", 1)
        expected_values = values_str.split(",")

        if qual_name not in qualifiers:
            return False

        qual_entries = qualifiers[qual_name]
        if not isinstance(qual_entries, list):
            return False

        for entry in qual_entries:
            value = _extract_qualifier_value(entry)
            if value in expected_values:
                return True

        return False

    return False


# === Entry Points ===


def validate_insdc_v2(
    json_data: dict[str, Any],
    *,
    strict: bool = False,
) -> list[ErrorDetail]:
    definition = load_insdc_definition()
    errors: list[ErrorDetail] = []

    # Validate features (non-source)
    features = json_data.get("features", [])
    for i, feature in enumerate(features):
        feature_type = feature.get("type", "")
        qualifiers = feature.get("qualifiers", {})
        loc_prefix: list[str | int] = ["features", i]

        # Phase 1: Feature key validation
        errors.extend(_validate_feature_key(definition, feature_type, loc_prefix, strict=strict))

        if feature_type not in definition.features:
            continue

        feature_def = definition.features[feature_type]

        # Phase 2: Qualifier key validation
        errors.extend(
            _validate_qualifier_keys(definition, feature_def, feature_type, qualifiers, loc_prefix, strict=strict)
        )

        # Phase 3: Value format validation (only for allowed qualifiers)
        allowed = set(feature_def.qualifiers.keys())
        errors.extend(_validate_qualifier_values(definition, qualifiers, loc_prefix, allowed_qualifiers=allowed))

        # Phase 3: Cross-constraint validation
        errors.extend(_validate_cross_constraints(definition, qualifiers, feature_type, loc_prefix))

    # Validate source qualifiers in common_source
    errors.extend(_validate_source_qualifiers_v2(json_data, definition, strict=strict))

    return errors


def _validate_source_qualifiers_v2(
    json_data: dict[str, Any],
    definition: InsdcDefinition,
    *,
    strict: bool,
) -> list[ErrorDetail]:
    errors: list[ErrorDetail] = []

    if "source" not in definition.features:
        return errors

    source_def = definition.features["source"]

    # In v2, organism and mol_type are required fields on Source model (not in qualifiers dict)
    v2_source_satisfied = {"organism", "mol_type"}

    # Validate common_source.qualifiers
    sequences = json_data.get("sequences", {})
    common_source = sequences.get("common_source", {})
    common_qualifiers = common_source.get("qualifiers", {})
    common_loc: list[str | int] = ["sequences", "common_source"]

    errors.extend(
        _validate_qualifier_keys(
            definition,
            source_def,
            "source",
            common_qualifiers,
            common_loc,
            strict=strict,
            skip_mandatory_as_warning=True,
            already_satisfied=v2_source_satisfied,
        )
    )
    source_allowed = set(source_def.qualifiers.keys())
    errors.extend(
        _validate_qualifier_values(definition, common_qualifiers, common_loc, allowed_qualifiers=source_allowed)
    )
    errors.extend(_validate_cross_constraints(definition, common_qualifiers, "source", common_loc))

    # Validate source_features[].source.qualifiers in each entry
    entries = sequences.get("entries", [])
    for entry_idx, entry in enumerate(entries):
        source_features = entry.get("source_features", [])
        for sf_idx, sf in enumerate(source_features):
            source = sf.get("source")
            if source is None:
                continue
            sf_qualifiers = source.get("qualifiers", {})
            sf_loc: list[str | int] = [
                "sequences",
                "entries",
                entry_idx,
                "source_features",
                sf_idx,
                "source",
            ]
            errors.extend(
                _validate_qualifier_keys(
                    definition,
                    source_def,
                    "source",
                    sf_qualifiers,
                    sf_loc,
                    strict=strict,
                    skip_mandatory_as_warning=True,
                    already_satisfied=v2_source_satisfied,
                )
            )
            errors.extend(
                _validate_qualifier_values(definition, sf_qualifiers, sf_loc, allowed_qualifiers=source_allowed)
            )

            # Cross-constraint: merge common_source + source_feature qualifiers
            merged_qualifiers = {**common_qualifiers, **sf_qualifiers}
            errors.extend(_validate_cross_constraints(definition, merged_qualifiers, "source", sf_loc))

    return errors


def validate_insdc_v1(
    json_data: dict[str, Any],
    *,
    strict: bool = False,
) -> list[ErrorDetail]:
    definition = load_insdc_definition()
    errors: list[ErrorDetail] = []

    v1_entries = json_data.get("ENTRIES", [])
    for entry_idx, entry in enumerate(v1_entries):
        features = entry.get("features", [])
        for feat_idx, feature in enumerate(features):
            feature_type = feature.get("type", "")
            qualifiers = feature.get("qualifiers", {})
            loc_prefix: list[str | int] = ["ENTRIES", entry_idx, "features", feat_idx]

            is_source = feature_type == "source"

            # Phase 1: Feature key validation
            errors.extend(_validate_feature_key(definition, feature_type, loc_prefix, strict=strict))

            if feature_type not in definition.features:
                continue

            feature_def = definition.features[feature_type]

            # Phase 2: Qualifier key validation
            errors.extend(
                _validate_qualifier_keys(
                    definition,
                    feature_def,
                    feature_type,
                    qualifiers,
                    loc_prefix,
                    strict=strict,
                    skip_mandatory_as_warning=is_source,
                )
            )

            # Phase 3: Value format validation (only for allowed qualifiers)
            allowed = set(feature_def.qualifiers.keys())
            errors.extend(
                _validate_qualifier_values(definition, qualifiers, loc_prefix, allowed_qualifiers=allowed)
            )

            # Phase 3: Cross-constraint validation
            errors.extend(_validate_cross_constraints(definition, qualifiers, feature_type, loc_prefix))

    return errors
