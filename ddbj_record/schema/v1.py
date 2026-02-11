from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Dblink(BaseModel):
    project: str = Field(examples=["PRJDB999999"])
    biosample: str = Field(examples=["SAMD999999"])
    sequence_read_archive: list[str] | None = Field(
        None,
        alias="sequence read archive",
        examples=["DRA999999"],
    )

    # extra field
    model_config = ConfigDict(extra="ignore")


class Submitter(BaseModel):
    ab_name: list[str] = Field(default_factory=list, examples=["Hiro,S."])
    contact: str = Field(examples=["Hiro Sue"])
    email: str = Field(examples=["hsue@example.com"])
    url: str | None = Field(None, examples=["http://example.com"])
    institute: str = Field(examples=["Example University"])
    department: str | None = Field(None, examples=["Example Department"])
    consrtm: str | None = Field(None, examples=["Example Consortium"])
    country: str = Field(examples=["Japan"])
    state: str | None = Field(None, examples=["Tokyo"])
    city: str = Field(examples=["Shinjuku"])
    street: str = Field(examples=["1-2-3 Example Street"])
    zip: str = Field(examples=["123-4567"])

    # extra field
    model_config = ConfigDict(extra="ignore")


class Reference(BaseModel):
    title: str = Field(examples=["Example Title"])
    ab_name: list[str] = Field(examples=["Hiro,S."])
    status: str = Field(examples=["Unpublished"])
    year: str = Field(examples=["2025"])

    # extra field
    model_config = ConfigDict(extra="ignore")


class Comment(BaseModel):
    line: list[str] = Field(default_factory=list, examples=["Example comment line 1", "Annotated by DFAST"])

    # extra field
    model_config = ConfigDict(extra="ignore")


class StComment(BaseModel):
    tagset_id: str = Field(examples=["Genome-Assembly-Data"])
    assembly_method: str = Field(
        alias="Assembly Method",
        examples=["HGAP v. x.x.x"],
    )
    coverage: str | None = Field(
        None,
        alias="Coverage",
        examples=["100x"],
    )
    genome_coverage: str | None = Field(
        None,
        alias="Genome Coverage",
        examples=["100x"],
    )
    sequencing_technology: str = Field(
        alias="Sequencing Technology",
        examples=["PacBio RS II"],
    )

    # extra field
    model_config = ConfigDict(extra="ignore")


class Date(BaseModel):
    hold_date: str = Field(examples=["2025-01-01"])

    # extra field
    model_config = ConfigDict(extra="ignore")


class Common(BaseModel):
    DBLINK: Dblink | None = Field(None)
    SUBMITTER: Submitter
    REFERENCE: list[Reference] = Field(default_factory=list)
    COMMENT: list[Comment] = Field(default_factory=list)
    ST_COMMENT: StComment
    DATE: Date | None = Field(None)
    trad_submission_category: Literal["WGS", "GNM"] = Field(
        description="if the submission is a draft genome, the value is 'WGS', and if it is a complete genome, the value is 'GNM'.",
        examples=["GNM"],
    )

    # extra field
    model_config = ConfigDict(extra="ignore")


class CommonSource(BaseModel):
    organism: str = Field(examples=["Paucilactobacillus hokkaidonensis"])
    mol_type: str = Field(examples=["genomic DNA"])

    # extra field
    model_config = ConfigDict(extra="allow")


class CommonMeta(BaseModel):
    division: str = Field(examples=["BCT"])
    locus_tag_prefix: str | None = Field(None, examples=["PLH"])
    dfast_version: str | None = Field(None, examples=["1.2.18"])
    seq_prefix: str | None = Field(
        None, examples=["sequence", "contig"], description="Prefix for sequence names. It is used when the data is WGS."
    )

    # extra field
    model_config = ConfigDict(extra="ignore")


class Feature(BaseModel):
    id: str = Field(examples=["feature_8"])
    type: str = Field(examples=["source"])
    location: str = Field(examples=["1..2277985"])
    qualifiers: dict[str, list[str | bool]] = Field(
        default_factory=dict,
        description="In addition to the information described in COMMON_SOURCE, information unique to each entry is described.",
    )
    locus_tag_id: str | None = Field(None, examples=["00010"])

    # extra field
    model_config = ConfigDict(extra="ignore")


class Entry(BaseModel):
    id: str = Field(
        examples=["chromosome"],
    )
    name: str = Field(
        description="The user-specified name of the sequence (e.g., contig1, contig2, etc. for draft genomes).",
        examples=["chromosome"],
    )
    type: Literal["chromosome", "plasmid", "unplaced", "other"] = Field(
        description="The type of the sequence (e.g., chromosome, plasmid, unplaced, other).",
        examples=["chromosome"],
    )
    topology: Literal["circular", "linear"] = Field(
        description="The topology of the sequence (e.g., linear, circular).",
        examples=["circular"],
    )
    sequence: str | None = Field(examples=["atgc..."])
    features: list[Feature] = Field(
        default_factory=list,
        description="The list of annotated biological features.",
    )

    # extra field
    model_config = ConfigDict(extra="forbid")


class DdbjRecord(BaseModel):
    schema_version: str = Field(examples=["v1.0"])

    COMMON: Common = Field(
        description="Corresponds to the COMMON section of the registered file (metadata common to all arrays, such as registrant information)"
    )
    COMMON_SOURCE: CommonSource = Field(description="Metadata common to all entries")
    COMMON_META: CommonMeta = Field(description="Metadata that DFAST internally handles")
    ENTRIES: list[Entry] = Field(default_factory=list)

    # extra field
    model_config = ConfigDict(extra="forbid")
