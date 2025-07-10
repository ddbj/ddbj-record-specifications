import json
from typing import Dict, List, Literal, Optional, Union

import jsonref
from pydantic import BaseModel, ConfigDict, Field

from ddbj_record_validator.utils import get_schema_dir_path


class Provenance(BaseModel):
    source_format: Optional[str] = Field(
        None,
        examples=["GFF3"],
        description="The original format of the input data, e.g., GFF3, Genbank, EMBL, etc.",
    )
    model_config = ConfigDict(extra="allow")


# Submitter (Organization, Grant, Consortium) あたりは、DRA, JGA, ヒトの OR を取る (日本語 and 英語の箱も含めて)
# そもそも論の最適な interface を決める
class Submitter(BaseModel):
    # ref.: https://www.ddbj.nig.ac.jp/ddbj/file-format.html#submitter
    ab_name: List[str] = Field(examples=["Mishima,H."])
    consrtm: Optional[str] = Field(None, examples=["Mouse Genome Consortium"])
    contact: str = Field(examples=["Hanako Mishima"])
    email: str = Field(examples=["mishima@ddbj.nig.ac.jp"])
    url: Optional[str] = Field(None, examples=["http://www.ddbj.nig.ac.jp"])
    institute: str = Field(examples=["National Institute of Genetics"])
    department: Optional[str] = Field(None, examples=["DNA Data Bank of Japan"])
    country: str = Field(examples=["Japan"])
    state: Optional[str] = Field(None, examples=["Shizuoka"])
    city: str = Field(examples=["Mishima"])
    street: str = Field(examples=["Yata 1111"])
    zip: str = Field(examples=["411-8540"])


class Dblink(BaseModel):
    # ref.: https://www.ddbj.nig.ac.jp/ddbj/file-format.html#dblink
    bioproject: str = Field(examples=["PRJDB999999"])
    biosample: str = Field(examples=["SAMD999999"])
    sequence_read_archive: List[str] = Field(
        default_factory=list,
        examples=["DRA999999"],
    )


class Reference(BaseModel):
    # ref.: https://www.ddbj.nig.ac.jp/ddbj/file-format.html#reference
    title: str = Field(examples=["Sequence and analysis of mouse ch.8"])
    ab_name: List[str] = Field(examples=["Mishima,H."])
    consrtm: Optional[str] = Field(None, examples=["Mouse Genome Consortium"])
    status: Literal["Unpublished", "In press", "Published"] = Field(examples=["Unpublished"])
    year: str = Field(examples=["2025"])
    journal: Optional[str] = Field(None, examples=["Nature"])
    volume: Optional[str] = Field(None, examples=["8"])
    start_page: Optional[str] = Field(None, examples=["15"])
    end_page: Optional[str] = Field(None, examples=["20"])


class Comment(BaseModel):
    # ref.: https://www.ddbj.nig.ac.jp/ddbj/file-format.html#comment
    line: List[str] = Field(examples=["Example comment line 1", "Annotated by DFAST"])


class Submission(BaseModel):
    # # trad_submission_category: Optional[Literal["WGS", "GNM"]] = Field(
    # #     description="If the submission is a draft genome, the value is 'WGS', and if it is a complete genome, the value is 'GNM'.",
    # #     examples=["GNM"],
    # # )
    # submission_category: Literal["WGS", "GNM", "MAG", "SAG", "TLS", "HTG", "TSA", "HTC", "EST"] = Field(
    #     examples=["WGS"]
    # )
    # # DFAST 的には、WGS or GNM だけど、record として、他の literal も許容できなければならない

    # datatype: Literal["WGS", "TLS", "TPA", "TPA-WGS"] = Field(examples=["WGS"])
    # division: Literal["CON", "ENV", "EST", "GSS", "HTC", "HTG", "STS", "SYN", "TSA"] = Field(examples=["EST"])

    # # ---

    locus_tag_prefix: str = Field(examples=["PLH"])
    hold_date: str = Field(examples=["20250101"])
    dblink: Dblink
    submitter: Submitter
    reference: List[Reference]
    comment: List[Comment]


class ExperimentGenomeAssemblyData(BaseModel):
    # ref.: https://www.ddbj.nig.ac.jp/ddbj/file-format.html#describing_st_comment
    tagset_id: Literal["Genome-Assembly-Data"] = Field(examples=["Genome-Assembly-Data"])
    assembly_method: str = Field(
        examples=["HGAP v. x.x.x"],
    )
    assembly_name: Optional[str] = Field(
        None,
        examples=["Mmus_1.0"],
    )
    genome_coverage: str = Field(
        examples=["100x"],
    )
    sequencing_technology: str = Field(
        examples=["PacBio RS II"],
    )


class ExperimentAssemblyData(BaseModel):
    # ref.: https://www.ddbj.nig.ac.jp/ddbj/file-format.html#describing_st_comment
    tagset_id: Literal["Assembly-Data"] = Field(examples=["Assembly-Data"])
    assembly_method: str = Field(
        examples=["HGAP v. x.x.x"],
    )
    assembly_name: Optional[str] = Field(
        None,
        examples=["Mmus_1.0"],
    )
    coverage: Optional[str] = Field(
        None,
        examples=["100x"],
    )
    sequencing_technology: str = Field(
        examples=["PacBio RS II"],
    )


class Qualifiers(BaseModel):
    # organism と mol_type 以外
    allele: str = Field(
        description="name of the allele for the given gene",
        examples=["adh1-1"]
    )
    altitude: str = Field(
        description="geographical altitude of the location from which the sample was collected",
        examples=["-256 m", "330.12 m"]
    )
    anticodon: str = Field(
        description="location of the anticodon of tRNA and the amino acid for which it codes",
        examples=["(pos:34..36,aa:Phe,seq:aaa)"]
    )
    # TODO 列挙 or コード的に、生成したい


class Source(BaseModel):
    # organism などもあくまで、qualifiers の一部として扱う
    organism: str = Field(examples=["Paucilactobacillus hokkaidonensis"])
    mol_type: str = Field(examples=["genomic DNA"])

    # TODO: 全ての qualifiers を optional で列挙する
    qualifiers: Qualifiers

    # or
    # {
    #     "qualifiers": [
    #         {
    #             "id": "id_of_qualifier",
    #             "key": "organism",
    #             "value": "Paucilactobacillus hokkaidonensis",
    #             // optional field(情報量を落とさないための field)
    #             "opt_field1": "opt_value1"
    #         }
    #     ]
    # }

    # model_config = ConfigDict(extra="allow")

    # type_material: Optional[str] = Field(None, examples=["type strain"])
    # collection_date: Optional[str] = Field(None, examples=["2012-04-01"])
    # culture_collection: Optional[str] = Field(None, examples=["JCM:18460"])
    # isolation_source: Optional[str] = Field(None, examples=["silage"])
    # geo_loc_name: str = Field(examples=["Japan:Hokkaido"])


# class Source(BaseModel):
#     organism: str = Field(examples=["Paucilactobacillus hokkaidonensis"])
#     strain: Optional[str] = Field(None, examples=["LOOC260"])
#     qualifies: SourceQualifiers


# organism と mol_type 以外の qualifiers を列挙する


class Entry(BaseModel):
    id: str = Field(
        examples=["chromosome"],
        description=" fasta の header の ID, 登録者の local ID, submitter sequence ID"
    )
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
    sequence: Optional[str] = Field(None, examples=["atgc..."])
    location: str = Field(examples=["1..2277985"])
    source: Optional[Source] = Field(
        None,
        description="Optional, 個別に書いた場合、この source が common_source を上書きする"
    )

    # 元 ff_definition
    definition: Optional[str]


class Sequences(BaseModel):
    common_source: Source
    entries: List[Entry]


class Feature(BaseModel):
    id: str = Field(examples=["feature_8"])
    type: str = Field(examples=["CDS"])
    location: str = Field(examples=["1..2277985"])
    sequence_id: str = Field(
        examples=["chromosome"],
        description="The ID of the sequence to which this feature belongs.",
    )
    # TODO: feature の type により、Qualifiers の Optional が Optional じゃなくなる
    # これは、jsonschema では表現できないため、コード的に表現する
    qualifiers: Qualifiers = Field(
        description="In addition to the information described in COMMON_SOURCE, information unique to each entry is described.",
    )


# class GffFeature(BaseModel):
#     id: str = Field(examples=["feature_8"])
#     type: str = Field(examples=["CDS"])
#     # TODO: 要確認 location?
#     location: str = Field(examples=["1..2277985"])
#     sequence_id: str = Field(
#         examples=["chromosome"],
#         description="The ID of the sequence to which this feature belongs.",
#     )
#     qualifiers: FeatureQualifiers = Field(
#         description="In addition to the information described in COMMON_SOURCE, information unique to each entry is described.",
#     )


class DdbjRecord(BaseModel):
    schema_version: str = Field(examples=["0.2.0"])
    provenance: Provenance = Field(
        description="""
        Metadata that records the origin and transformation history of the data.
        It includes details such as the software used for conversion, timestamps and input sources to ensure traceability and reproducibility of the dataset.
        """
    )
    submission: Submission
    # experiment の構造は、JGA, DRA の構造から引用したほうがいいかもしれない
    # experiment は、List[Experiment] かもしれない
    # experiment: ExperimentGenomeAssemblyData | ExperimentAssemblyData
    sequences: Sequences
    features: List[Feature]
    # features: List[Feature | GffFeature]


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
