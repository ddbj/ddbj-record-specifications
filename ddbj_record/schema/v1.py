from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ddbj_record.schema import LEGACY_SCHEMA_VERSION_MAP


class Dblink(BaseModel):
    project: str = Field(examples=["PRJDB999999"])
    biosample: str = Field(examples=["SAMD999999"])
    sequence_read_archive: Optional[List[str]] = Field(
        None,
        alias="sequence read archive",
        examples=["DRA999999"],
    )

    # extra field
    model_config = ConfigDict(extra="ignore")


class Submitter(BaseModel):
    ab_name: List[str] = Field(default_factory=list, examples=["Hiro,S."])
    contact: str = Field(examples=["Hiro Sue"])
    email: str = Field(examples=["hsue@example.com"])
    url: Optional[str] = Field(None, examples=["http://example.com"])
    institute: str = Field(examples=["Example University"])
    department: Optional[str] = Field(None, examples=["Example Department"])
    consrtm: Optional[str] = Field(None, examples=["Example Consortium"])
    country: str = Field(examples=["Japan"])
    state: Optional[str] = Field(None, examples=["Tokyo"])
    city: str = Field(examples=["Shinjuku"])
    street: str = Field(examples=["1-2-3 Example Street"])
    zip: str = Field(examples=["123-4567"])

    # extra field
    model_config = ConfigDict(extra="ignore")


class Reference(BaseModel):
    title: str = Field(examples=["Example Title"])
    ab_name: List[str] = Field(examples=["Hiro,S."])
    status: str = Field(examples=["Unpublished"])
    year: str = Field(examples=["2025"])

    # extra field
    model_config = ConfigDict(extra="ignore")


class Comment(BaseModel):
    line: List[str] = Field(default_factory=list, examples=["Example comment line 1", "Annotated by DFAST"])

    # extra field
    model_config = ConfigDict(extra="ignore")


class StComment(BaseModel):
    tagset_id: str = Field(examples=["Genome-Assembly-Data"])
    assembly_method: str = Field(
        alias="Assembly Method",
        examples=["HGAP v. x.x.x"],
    )
    coverage: Optional[str] = Field(
        None,
        alias="Coverage",
        examples=["100x"],
    )
    genome_coverage: Optional[str] = Field(
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
    DBLINK: Optional[Dblink] = Field(None)
    SUBMITTER: Submitter
    REFERENCE: List[Reference] = Field(default_factory=list)
    COMMENT: List[Comment] = Field(default_factory=list)
    ST_COMMENT: StComment
    DATE: Optional[Date] = Field(None)
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
    locus_tag_prefix: Optional[str] = Field(None, examples=["PLH"])
    dfast_version: Optional[str] = Field(None, examples=["1.2.18"])
    seq_prefix: Optional[str] = Field(
        None,
        examples=["sequence", "contig"],
        description="Prefix for sequence names. It is used when the data is WGS."
    )

    # extra field
    model_config = ConfigDict(extra="ignore")


class Feature(BaseModel):
    id: str = Field(examples=["feature_8"])
    type: str = Field(examples=["source"])
    location: str = Field(examples=["1..2277985"])
    qualifiers: Dict[str, List[Union[str, bool]]] = Field(
        default_factory=dict,
        description="In addition to the information described in COMMON_SOURCE, information unique to each entry is described.",
    )
    locus_tag_id: Optional[str] = Field(None, examples=["00010"])

    # extra field
    model_config = ConfigDict(extra="ignore")


class Entry(BaseModel):
    id: str = Field(examples=["chromosome"],)
    name: str = Field(
        description="The user-specified name of the sequence (e.g., contig1, contig2, etc. for draft genomes).",
        examples=["chromosome"]
    )
    type: Literal["chromosome", "plasmid", "unplaced", "other"] = Field(
        description="The type of the sequence (e.g., chromosome, plasmid, unplaced, other).",
        examples=["chromosome"],
    )
    topology: Literal["circular", "linear"] = Field(
        description="The topology of the sequence (e.g., linear, circular).",
        examples=["circular"],
    )
    sequence: Optional[str] = Field(examples=["atgc..."])
    features: List[Feature] = Field(
        default_factory=list,
        description="The list of annotated biological features.",
    )

    # extra field
    model_config = ConfigDict(extra="forbid")


class DdbjRecord(BaseModel):
    schema_version: str = Field(examples=["v1.0"])

    @field_validator("schema_version", mode="before")
    @classmethod
    def normalize_schema_version(cls, v: str) -> str:
        return LEGACY_SCHEMA_VERSION_MAP.get(v, v)

    COMMON: Common = Field(
        description="Corresponds to the COMMON section of the registered file (metadata common to all arrays, such as registrant information)"
    )
    COMMON_SOURCE: CommonSource = Field(
        description="Metadata common to all entries"
    )
    COMMON_META: CommonMeta = Field(
        description="Metadata that DFAST internally handles"
    )
    ENTRIES: List[Entry] = Field(default_factory=list)

    # extra field
    model_config = ConfigDict(extra="forbid")
