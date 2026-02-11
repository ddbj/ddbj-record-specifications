"""Pydantic models for the INSDC feature/qualifier definition YAML."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


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


class CrossConstraint(BaseModel):
    type: Literal["mutual_exclusion", "dependency", "exclusion", "conditional_mandatory"]
    qualifiers: list[str] | None = None
    qualifier: str | None = None
    requires: str | list[str] | None = None
    feature: str | None = None
    condition: str | None = None
    then_mandatory: list[str] | None = None
    message: str


class Meta(BaseModel):
    insdc_version: str
    generated_at: str
    sources: list[str]


class InsdcDefinition(BaseModel):
    meta: Meta
    qualifiers: dict[str, QualifierDefinition]
    features: dict[str, FeatureDefinition]
    cross_constraints: list[CrossConstraint]
