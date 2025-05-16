import json
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from ddbj_record_validator.utils import get_schema_dir_path


class Datatype(BaseModel):
    type: Literal["WGS", "GNM"] = Field(
        description="if the submission is a draft genome, the value is 'WGS', and if it is a complete genome, the value is 'GNM'.",
    )


class Keyword(BaseModel):
    keyword: List[str]


class Dblink(BaseModel):
    project: str = Field(examples=["PRJDB999999"])
    biosample: str = Field(examples=["SAMD999999"])
    sequence_read_archive: Optional[List[str]] = Field(
        None,
        alias="sequence read archive",
        examples=["DRA999999"],
    )


class Submitter(BaseModel):
    ab_name: List[str] = Field(examples=["Hiro,S."])
    contact: str = Field(examples=["Hiro Sue"])
    email: str = Field(examples=["hsue@example.com"])
    url: Optional[str] = Field(None, examples=["http://example.com"])
    institute: str = Field(examples=["Example University"])
    department: Optional[str] = Field(None, examples=["Example Department"])
    country: str = Field(examples=["Japan"])
    state: Optional[str] = Field(None, examples=["Tokyo"])
    city: str = Field(examples=["Shinjuku"])
    street: str = Field(examples=["1-2-3 Example Street"])
    zip: str = Field(examples=["123-4567"])


class Reference(BaseModel):
    title: str = Field(examples=["Example Title"])
    ab_name: List[str] = Field(examples=["Hiro,S."])
    status: str = Field(examples=["Unpublished"])
    year: str = Field(examples=["2025"])


class Comment(BaseModel):
    line: List[str] = Field(examples=["Example comment line 1", "Annotated by DFAST"])


class StComment(BaseModel):
    tagset_id: str = Field(examples=["Genome-Assembly-Data"])
    assembly_method: str = Field(
        alias="Assembly Method",
        examples=["HGAP v. x.x.x"],
    )
    genome_coverage: str = Field(
        alias="Genome Coverage",
        examples=["100x"],
    )
    sequencing_technology: str = Field(
        alias="Sequencing Technology",
        examples=["PacBio RS II"],
    )


class Date(BaseModel):
    hold_date: str = Field(examples=["2025-01-01"])


class Common(BaseModel):
    DATATYPE: Datatype
    KEYWORD: Keyword
    DBLINK: Dblink
    SUBMITTER: Submitter
    REFERENCE: List[Reference]
    COMMENT: List[Comment]
    ST_COMMENT: StComment
    DATE: Optional[Date] = Field(None)
    trad_submission_category: Literal["WGS", "GNM"] = Field(
        description="if the submission is a draft genome, the value is 'WGS', and if it is a complete genome, the value is 'GNM'.",
        examples=["GNM"],
    )


class CommonSource(BaseModel):
    organism: str = Field(examples=["Paucilactobacillus hokkaidonensis"])
    strain: Optional[str] = Field(None, examples=["LOOC260"])
    mol_type: str = Field(examples=["genomic DNA"])
    type_material: Optional[str] = Field(None, examples=["type strain"])
    collection_date: Optional[str] = Field(None, examples=["2012-04-01"])
    culture_collection: Optional[str] = Field(None, examples=["JCM:18460"])
    isolation_source: Optional[str] = Field(None, examples=["silage"])
    geo_loc_name: str = Field(examples=["Japan:Hokkaido"])


class CommonMeta(BaseModel):
    division: str = Field(examples=["BCT"])
    locus_tag_prefix: str = Field(examples=["PLH"])


class Feature(BaseModel):
    id: str = Field(examples=["feature_8"])
    type: str = Field(examples=["source"])
    location: str = Field(examples=["1..2277985"])
    qualifiers: Dict[str, List[str]] = Field(
        description="In addition to the information described in COMMON_SOURCE, information unique to each entry is described.",
    )
    locus_tag_id: Optional[str] = Field(None, examples=["00010"])


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
        description="The list of annotated biological features.",
    )


class DdbjRecord(BaseModel):
    schema_version: str = Field(examples=["0.1"])
    COMMON: Common = Field(
        description="Corresponds to the COMMON section of the registered file (metadata common to all arrays, such as registrant information)"
    )
    COMMON_SOURCE: CommonSource = Field(
        description="Metadata common to all entries"
    )
    COMMON_META: CommonMeta = Field(
        description="Metadata that DFAST internally handles"
    )
    ENTRIES: List[Entry]


# === CLI ===

def main() -> None:
    schema_dir_path = get_schema_dir_path()
    schema_path = schema_dir_path.joinpath("v1.0/ddbj_record.schema.json")
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_dict = DdbjRecord.model_json_schema()
    with schema_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(schema_dict, indent=2))


if __name__ == "__main__":
    main()
