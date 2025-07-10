import json
from typing import Dict, List, Literal, Optional

import jsonref  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field

from ddbj_record_validator.utils import get_schema_dir_path


# TODO: discussion
class Provenance(BaseModel):
    source_format: Optional[str] = Field(
        None,
        examples=["GFF3"],
        description="The original format of the input data, e.g., GFF3, Genbank, EMBL, etc.",
    )

    # extra field
    model_config = ConfigDict(extra="allow")


# === Submission ===


# TODO: update
class Address(BaseModel):
    country: str = Field(..., examples=["Japan"])
    state: Optional[str] = Field(None, examples=["Shizuoka"])
    city: str = Field(..., examples=["Mishima"])
    street: Optional[str] = Field(None, examples=["Yata 1111"])
    postal_code: Optional[str] = Field(None, examples=["411-8540"])


class Organization(BaseModel):
    name: str = Field(..., examples=["National Institute of Genetics"])
    abbreviation: Optional[str] = Field(None, examples=["NIG"])
    url: Optional[str] = Field(None, examples=["http://www.ddbj.nig.ac.jp"])
    role: Optional[str] = Field(None, examples=["owner"])  # TODO: Update enum from bs xml, etc. Organization に role がつくのがわからない。でも、BS がそうなっている
    type: Optional[Literal["institution", "company", "government", "non-profit", "consortium", "other"]] = Field(
        None,
        examples=["institution"],
    )   # TODO: Update enum from bs xml, etc.
    address: Optional[Address]
    ror_id: Optional[str] = Field(
        None,
        examples=["https://ror.org/01xq5f0"],
    )


class Person(BaseModel):
    name: str = Field(..., examples=["Hanako Mishima"])
    abbreviation: Optional[str] = Field(None, examples=["Mishima,H."])
    email: str = Field(..., examples=["mishima@ddbj.nig.ac.jp"])
    orcid: Optional[str] = Field(None, examples=["0000-0000-0000-0000"])
    organization: Organization


class Xref(BaseModel):
    db: Literal["BioProject", "BioSample", "DRA", "ENA", "GenBank", "RefSeq"] = Field(
        examples=["BioProject"],
    )  # TODO: Update enum from bs / bp, etc.
    id: str = Field(
        examples=["PRJDB999999"],
        description="The accession number of the database.",
    )
    relation_type: Optional[Literal[
        "is_part_of",
        "has_part",
        "is_derived_from",
        "is_associated_with",
        "represents",
        "replaces",
        "is_replaced_by",
        "is_equivalent_to",  # or same_as?
        "was_used_by",
        "is_version_of",
        "is_metadata_for",
        "is_input_of",
        "is_output_of",
    ]] = Field(
        None,
        examples=["is_part_of"],
    )  # TODO: discussion


class Reference(BaseModel):
    title: str = Field(examples=["Sequence and analysis of mouse ch.8"])
    authors: List[Person]
    consortiums: List[Organization]
    status: Literal["Unpublished", "In press", "Published"] = Field(examples=["Unpublished"])
    year: str = Field(examples=["2025"])
    journal: Optional[str] = Field(None, examples=["Nature"])
    volume: Optional[str] = Field(None, examples=["8"])
    issue: Optional[str] = Field(None, examples=["1"])
    start_page: Optional[str] = Field(None, examples=["15"])
    end_page: Optional[str] = Field(None, examples=["20"])
    date_published: Optional[str] = Field(None, examples=["2025-01-01"])
    doi: Optional[str] = Field(None, examples=["10.1038/nature12345"])
    url: Optional[str] = Field(None, examples=["https://doi.org/10.1038/nature12345"])
    pubmed_id: Optional[str] = Field(None, examples=["12345678"])


class Submission(BaseModel):
    submitters: List[Person]
    db_xrefs: List[Xref]
    references: List[Reference]
    comments: List[str] = Field(examples=["Example comment line 1", "Annotated by DFAST"])

    # TODO: discussion (DFAST 的には、WGS or GNM だけど、record として、他の literal も許容できなければならない、実は階層構造だし、Literal も不十分)
    trad_submission_category: Optional[Literal["WGS", "GNM"]] = Field(
        description="If the submission is a draft genome, the value is 'WGS', and if it is a complete genome, the value is 'GNM'.",
        examples=["GNM"],
    )
    submission_category: Literal["WGS", "GNM", "MAG", "SAG", "TLS", "HTG", "TSA", "HTC", "EST"] = Field(
        examples=["WGS"]
    )
    datatype: Literal["WGS", "TLS", "TPA", "TPA-WGS"] = Field(examples=["WGS"])
    division: Literal["CON", "ENV", "EST", "GSS", "HTC", "HTG", "STS", "SYN", "TSA"] = Field(examples=["EST"])

    locus_tag_prefix: str = Field(examples=["PLH"])
    hold_date: str = Field(examples=["2025-01-01"])


# === Experiment (主に JGA から) ===


class LibraryLayout(BaseModel):
    type: Literal["SINGLE", "PAIRED"]
    nominal_length: Optional[int]
    nominal_sdev: Optional[float]


class LibraryDescriptor(BaseModel):
    library_name: Optional[str]
    library_strategy: str = Field(..., examples=["WGS", "RNA-Seq", "ChIP-Seq", "ATAC-Seq"])  # TODO: Enumerate (e.g., WGS, RNA-Seq, etc.)
    library_source: str
    library_selection: str
    library_layout: Optional[LibraryLayout]
    targeted_loci: Optional[List[str]]
    library_construction_protocol: Optional[str]


class Library(BaseModel):
    design_description: Optional[str]
    descriptor: LibraryDescriptor


class SequencingPlatform(BaseModel):
    instrument_model: str = Field(..., examples=["PacBio RS II", "Illumina HiSeq 2500"])


class ArrayPlatform(BaseModel):
    model: str = Field(..., examples=["Affymetrix GeneChip Mouse Genome 430 2.0 Array"])


class ExperimentPlatform(BaseModel):
    sequencing: Optional[SequencingPlatform]
    array: Optional[ArrayPlatform]


class ExperimentLink(BaseModel):
    label: Optional[str]
    url: Optional[str]


class ExperimentAttribute(BaseModel):
    tag: str = Field(..., examples=["assembly_method", "genome_coverage"])
    value: str = Field(..., examples=["HGAP v. x.x.x", "100x"])
    description: Optional[str]


class Experiment(BaseModel):
    title: Optional[str] = Field(None, examples=["Genome Assembly of Mmus_1.0"])
    design: Library
    platform: Optional[ExperimentPlatform]
    experiment_links: Optional[List[ExperimentLink]]
    experiment_attributes: Optional[List[ExperimentAttribute]]


# === Sequences ===


class Qualifier(BaseModel):
    id: Optional[str] = Field(None, examples=["qualifier_1"])
    value: str = Field(..., examples=["Paucilactobacillus hokkaidonensis", "genomic DNA"])  # TODO: discussion true or false なども存在する
    note: Optional[str] = Field(None, examples=["This is a note for the qualifier."])
    ontology_term: Optional[str] = Field(None, examples=["NCIT:C12345"])  # TODO: discussion, OBO term とか、いらない気もする

    # extra field
    model_config = ConfigDict(extra="allow")


class Source(BaseModel):
    # TODO: organism と mol_type を独立させるか迷っている (source においては必須項目)
    organism: str = Field(examples=["Paucilactobacillus hokkaidonensis"])
    mol_type: str = Field(examples=["genomic DNA"])
    qualifiers: Dict[str, List[Qualifier]]  # Key is qualifier key


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

    definition: Optional[List[str]]  # TODO: 元 ff_definition、そもそも消すとか、構造を変えるという話もある


class Sequences(BaseModel):
    common_source: Source
    entries: List[Entry]


# === Feature ===


class Feature(BaseModel):
    id: str = Field(examples=["feature_8"])
    type: str = Field(examples=["CDS"])  # TODO: Enumerate (e.g., CDS, gene, rRNA, tRNA, etc.)
    location: str = Field(examples=["1..2277985"])
    sequence_id: str = Field(
        examples=["chromosome"],
        description="The ID of the sequence to which this feature belongs.",
    )
    qualifiers: Dict[str, List[Qualifier]] = Field(
        description="In addition to the information described in COMMON_SOURCE, information unique to each entry is described.",
    )  # Key is qualifier key


# === DDBJ Record ===


class DdbjRecord(BaseModel):
    schema_version: str = Field(examples=["v2"])
    provenance: Provenance = Field(
        description="""
        Metadata that records the origin and transformation history of the data.
        It includes details such as the software used for conversion, timestamps and input sources to ensure traceability and reproducibility of the dataset.
        """
    )
    submission: Submission
    experiments: List[Experiment]
    sequences: Sequences
    features: List[Feature]


# === CLI ===


def main() -> None:
    schema_dir_path = get_schema_dir_path()
    schema_path = schema_dir_path.joinpath("v2/ddbj_record.schema.json")
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_dict = DdbjRecord.model_json_schema()
    resolved_schema = jsonref.loads(json.dumps(schema_dict))
    resolved_schema_dict = dict(resolved_schema)
    del resolved_schema_dict["$defs"]
    with schema_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(resolved_schema_dict, indent=2))


if __name__ == "__main__":
    main()
