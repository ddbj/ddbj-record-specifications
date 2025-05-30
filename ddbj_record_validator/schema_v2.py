import json
from typing import Dict, List, Literal, Optional

import jsonref
from pydantic import BaseModel, Field

from ddbj_record_validator.utils import get_schema_dir_path


class Provenance(BaseModel):
    pass


class Dblink(BaseModel):
    bioproject: str = Field(examples=["PRJDB999999"])
    biosample: str = Field(examples=["SAMD999999"])
    sequence_read_archive: Optional[List[str]] = Field(
        None,
        examples=["DRA999999"],
    )


class Submitter(BaseModel):
    # ref.: https://www.ddbj.nig.ac.jp/ddbj/file-format.html#submitter
    # TODO: 使用可能文字や文字数上限は上のリンクを参照する
    # TODO: jsonschema level で書くか、別の validator を作るかは要 discussion
    url: Optional[str] = Field(None, examples=["http://example.com"])
    ab_name: List[str] = Field(examples=["Hiro,S."])
    contact: str = Field(examples=["Hiro Sue"])
    email: str = Field(examples=["hsue@example.com"])
    institute: str = Field(examples=["Example University"])
    department: Optional[str] = Field(None, examples=["Example Department"])
    country: str = Field(examples=["Japan"])
    state: Optional[str] = Field(None, examples=["Tokyo"])
    city: str = Field(examples=["Shinjuku"])
    street: str = Field(examples=["1-2-3 Example Street"])
    zip: str = Field(examples=["123-4567"])


class Reference(BaseModel):
    # ref.: https://www.ddbj.nig.ac.jp/ddbj/file-format.html#reference
    # TODO: 使用可能文字や文字数上限は上のリンクを参照する
    title: str = Field(examples=["Example Title"])
    ab_name: List[str] = Field(examples=["Hiro,S."])
    status: Literal["Unpublished", "In press", "Published"] = Field(examples=["Unpublished"])
    year: str = Field(examples=["2025"])
    journal: Optional[str]
    volume: Optional[str]
    start_page: Optional[str]
    end_page: Optional[str]


class Comment(BaseModel):
    # ref.: https://www.ddbj.nig.ac.jp/ddbj/file-format.html#comment
    line: List[str] = Field(examples=["Example comment line 1", "Annotated by DFAST"])


class Submission(BaseModel):
    trad_submission_category: Literal["WGS", "GNM"] = Field(
        description="If the submission is a draft genome, the value is 'WGS', and if it is a complete genome, the value is 'GNM'.",
        examples=["GNM"],
    )  # from Common / Datatype
    # ref.: https://www.ddbj.nig.ac.jp/ddbj/file-format.html#division
    # BCT ではないよね
    division: str = Field(examples=["BCT"])  # from CommonMeta
    locus_tag_prefix: str = Field(examples=["PLH"])  # from CommonMeta
    # ref.: https://www.ddbj.nig.ac.jp/ddbj/file-format.html#date
    hold_date: str = Field(examples=["20250101"])  # from Common
    dblink: Dblink  # from Common
    submitter: Submitter  # from Common
    reference: List[Reference]  # from Common
    # ref.: https://www.ddbj.nig.ac.jp/ddbj/file-format.html#comment
    comment: List[Comment]  # from Common


class Experiment(BaseModel):  # from Common/StComment
    # ref.: https://www.ddbj.nig.ac.jp/ddbj/file-format.html#comment
    # https://www.ddbj.nig.ac.jp/ddbj/file-format.html#describing_st_comment
    # TODO: tagset_id ごとに、必須項目が異なる、詳細は、上のリンク
    tagset_id: str = Field(examples=["Genome-Assembly-Data"])
    assembly_method: Optional[str] = Field(
        examples=["HGAP v. x.x.x"],
    )
    assembly_name: Optional[str] = Field(
        examples=["Mmus_1.0"],
    )
    genome_coverage: Optional[str] = Field(
        examples=["100x"],
    )
    sequencing_technology: Optional[str] = Field(
        examples=["PacBio RS II"],
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


class SourceQualifiers(BaseModel):
    # Source の Qualifier
    pass


class Source(BaseModel):
    organism: str = Field(examples=["Paucilactobacillus hokkaidonensis"])
    strain: Optional[str] = Field(None, examples=["LOOC260"])
    qualifies: SourceQualifiers


class Entry(BaseModel):
    id: str = Field(examples=["chromosome"],
                    description=" fasta の header の ID, 登録者の local ID, submitter sequence ID")
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
    location: str = Field(examples=["1..2277985"])
    source: Optional[Source] = Field(
        description="Optional, 個別に書いた場合、この source が common_source を上書きする"
    )


class Sequence(BaseModel):
    common_source: CommonSource  # from CommonSource
    entries: List[Entry]


class FeatureQualifiers(BaseModel):
    # Feature の Qualifier
    pass


class Feature(BaseModel):
    # これの ID は？
    id: str = Field(examples=["feature_8"])
    type: str = Field(examples=["CDS"])
    # TODO: 要確認 location?
    location: str = Field(examples=["1..2277985"])
    sequence_id: str = Field(
        examples=["chromosome"],
        description="The ID of the sequence to which this feature belongs.",
    )
    qualifiers: FeatureQualifiers = Field(
        description="In addition to the information described in COMMON_SOURCE, information unique to each entry is described.",
    )


class GffFeature(BaseModel):
    id: str = Field(examples=["feature_8"])
    type: str = Field(examples=["CDS"])
    # TODO: 要確認 location?
    location: str = Field(examples=["1..2277985"])
    sequence_id: str = Field(
        examples=["chromosome"],
        description="The ID of the sequence to which this feature belongs.",
    )
    qualifiers: FeatureQualifiers = Field(
        description="In addition to the information described in COMMON_SOURCE, information unique to each entry is described.",
    )


# Feature が GFF ように extend される


class DdbjRecord(BaseModel):
    schema_version: str = Field(examples=["0.2"])
    provenance: Provenance
    submission: Submission
    experiment: Experiment
    sequence: Sequence
    features: List[Feature | GffFeature]


# === CLI ===


def main() -> None:
    schema_dir_path = get_schema_dir_path()
    schema_path = schema_dir_path.joinpath("v2.0/ddbj_record.schema.json")
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_dict = DdbjRecord.model_json_schema()
    resolved_schema = jsonref.loads(json.dumps(schema_dict))
    resolved_schema_dict = dict(resolved_schema)
    del resolved_schema_dict["$defs"]
    with schema_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(resolved_schema_dict, indent=2))


if __name__ == "__main__":
    main()
