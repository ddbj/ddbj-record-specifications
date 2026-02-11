"""Pydantic models for the INSDC feature/qualifier definition YAML."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Discriminator


class DeprecatedInfo(BaseModel):
    replacement: str | None = None
    message: str


class QualifierDefinition(BaseModel):
    value_format: Literal["text", "controlled_vocabulary", "none", "structured"]
    description: str
    controlled_vocabulary: list[str] | None = None
    deprecated: DeprecatedInfo | None = None
    regex: str | None = None


class FeatureDefinition(BaseModel):
    description: str
    qualifiers: dict[str, Literal["mandatory", "optional"]]


# === Cross-Constraint Discriminated Union ===


class MutualExclusionConstraint(BaseModel):
    type: Literal["mutual_exclusion"] = "mutual_exclusion"
    qualifiers: list[str]
    message: str


class DependencyConstraint(BaseModel):
    type: Literal["dependency"] = "dependency"
    qualifier: str
    requires: str | list[str]
    message: str


class ConditionalMandatoryConstraint(BaseModel):
    type: Literal["conditional_mandatory"] = "conditional_mandatory"
    feature: str | None = None
    condition: str
    then_mandatory: list[str]
    message: str


CrossConstraint = Annotated[
    MutualExclusionConstraint | DependencyConstraint | ConditionalMandatoryConstraint,
    Discriminator("type"),
]


class Meta(BaseModel):
    insdc_version: str
    generated_at: str
    sources: list[str]


class InsdcDefinition(BaseModel):
    meta: Meta
    qualifiers: dict[str, QualifierDefinition]
    features: dict[str, FeatureDefinition]
    cross_constraints: list[CrossConstraint]
