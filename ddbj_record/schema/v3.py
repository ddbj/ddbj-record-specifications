from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# === Common types ===


class Organism(BaseModel):
    name: str | None = Field(None, examples=["Homo sapiens"])
    taxonomy_id: int | None = Field(None, examples=[9606])

    model_config = ConfigDict(extra="forbid")


class Address(BaseModel):
    country: str | None = Field(None, examples=["Japan"])
    state: str | None = Field(None, examples=["Shizuoka"])
    city: str | None = Field(None, examples=["Mishima"])
    street: str | None = Field(None, examples=["Yata 1111"])
    postal_code: str | None = Field(None, examples=["411-8540"])

    model_config = ConfigDict(extra="forbid")


class Organization(BaseModel):
    name: str | None = Field(None, examples=["National Institute of Genetics"])
    abbreviation: str | None = Field(None, examples=["NIG"])
    url: str | None = Field(None, examples=["http://www.ddbj.nig.ac.jp"])
    role: str | None = Field(None, examples=["owner"])
    type: str | None = Field(None, examples=["institution"])
    department: str | None = Field(
        None, examples=["DNA Data Bank of Japan"]
    )
    address: Address | None = None
    ror_id: str | None = Field(None, examples=["https://ror.org/01xq5f0"])

    model_config = ConfigDict(extra="forbid")


class Person(BaseModel):
    name: str | None = Field(None, examples=["Hanako Mishima"])
    first_name: str | None = Field(None, examples=["Hanako"])
    last_name: str | None = Field(None, examples=["Mishima"])
    abbreviation: str | None = Field(None, examples=["Mishima,H."])
    email: str | None = Field(None, examples=["mishima@ddbj.nig.ac.jp"])
    phone: str | None = None
    orcid: str | None = Field(None, examples=["0000-0000-0000-0000"])
    role: str | None = Field(None, examples=["submitter"])
    organizations: list[Organization] | None = None

    model_config = ConfigDict(extra="forbid")


# === Provenance ===


class GffMeta(BaseModel):
    version: str | None = Field(None, examples=["3"])
    pragmas: list[str] | None = None
    source_tool: str | None = Field(None, examples=["DFAST"])

    model_config = ConfigDict(extra="forbid")


class Provenance(BaseModel):
    source_format: str | None = Field(None, examples=["GFF"])
    submission_category: str | None = Field(
        None, examples=["WGS"]
    )
    gff: GffMeta | None = None

    model_config = ConfigDict(extra="allow")


# === Submission ===


class Submission(BaseModel):
    submitters: list[Person] | None = None
    hold_date: str | None = Field(None, examples=["2025-01-01"])
    comments: list[str] | None = None

    model_config = ConfigDict(extra="forbid")


# === Project ===


class Publication(BaseModel):
    title: str | None = None
    pubmed_id: str | None = Field(None, examples=["12345678"])
    doi: str | None = Field(None, examples=["10.1038/nature12345"])
    status: str | None = Field(None, examples=["published"])
    date: str | None = Field(None, examples=["2025-01-01"])
    journal: str | None = Field(None, examples=["Nature"])
    volume: str | None = None
    issue: str | None = None
    pages_from: str | None = None
    pages_to: str | None = None
    authors: list[Person] | None = None

    model_config = ConfigDict(extra="forbid")


class Grant(BaseModel):
    title: str | None = None
    agency: str | None = None
    id: str | None = None

    model_config = ConfigDict(extra="forbid")


class ProjectTarget(BaseModel):
    sample_scope: str | None = Field(None, examples=["monoisolate"])
    material: str | None = Field(None, examples=["genome"])
    capture: str | None = Field(None, examples=["whole"])
    method: str | None = Field(None, examples=["sequencing"])
    data_types: list[str] | None = None

    model_config = ConfigDict(extra="forbid")


class Project(BaseModel):
    accession: str | None = Field(None, examples=["PRJDB12345"])
    alias: str | None = None
    title: str | None = None
    description: str | None = None
    project_type: str | None = Field(None, examples=["primary"])
    study_types: list[str] | None = None
    organism: Organism | None = None
    publications: list[Publication] | None = None
    grants: list[Grant] | None = None
    keywords: list[str] | None = None
    relevance: dict[str, str] | None = None
    locus_tag_prefix: list[str] | None = None
    target: ProjectTarget | None = None

    model_config = ConfigDict(extra="forbid")


# === Sample ===


class Attribute(BaseModel):
    name: str | None = None
    value: str | None = None
    unit: str | None = None

    model_config = ConfigDict(extra="forbid")


class Sample(BaseModel):
    accession: str | None = Field(None, examples=["SAMD00123456"])
    alias: str | None = None
    title: str | None = None
    organism: Organism | None = None
    attributes: list[Attribute] | None = None
    package: str | None = Field(None, examples=["MIGS.ba"])
    donor_id: str | None = None
    sample_group_type: str | None = Field(None, examples=["case"])

    model_config = ConfigDict(extra="forbid")


# === Experiment ===


class LibraryDescriptor(BaseModel):
    name: str | None = None
    strategy: str | None = Field(None, examples=["WGS"])
    source: str | None = Field(None, examples=["GENOMIC"])
    selection: str | None = Field(None, examples=["RANDOM"])
    layout: str | None = Field(None, examples=["paired"])
    nominal_length: int | None = None
    nominal_sdev: float | None = None
    construction_protocol: str | None = None

    model_config = ConfigDict(extra="forbid")


class Platform(BaseModel):
    type: str | None = Field(None, examples=["ILLUMINA"])
    instrument_model: str | None = Field(
        None, examples=["Illumina HiSeq 2500"]
    )
    array_name: str | None = None
    array_description: str | None = None
    array_provider: str | None = None

    model_config = ConfigDict(extra="forbid")


class Experiment(BaseModel):
    accession: str | None = Field(None, examples=["DRX000001"])
    alias: str | None = None
    title: str | None = None
    library: LibraryDescriptor | None = None
    platform: Platform | None = None
    targeted_loci: list[str] | None = None

    model_config = ConfigDict(extra="forbid")


# === Run ===


class File(BaseModel):
    filename: str | None = None
    filetype: str | None = Field(None, examples=["fastq"])
    checksum_method: str | None = Field(None, examples=["MD5"])
    checksum: str | None = None

    model_config = ConfigDict(extra="forbid")


class Run(BaseModel):
    accession: str | None = Field(None, examples=["DRR000001"])
    alias: str | None = None
    title: str | None = None
    run_date: str | None = None
    data_type: str | None = Field(None, examples=["sequencing"])
    files: list[File] | None = None

    model_config = ConfigDict(extra="forbid")


# === Analysis ===


class Analysis(BaseModel):
    accession: str | None = Field(None, examples=["DRZ000001"])
    alias: str | None = None
    title: str | None = None
    analysis_type: str | None = Field(
        None, examples=["de_novo_assembly"]
    )
    analysis_date: str | None = None
    files: list[File] | None = None

    model_config = ConfigDict(extra="forbid")


# === Sequences & Entries ===


class Qualifier(BaseModel):
    alias: str | None = None
    value: str | None = None

    model_config = ConfigDict(extra="forbid")


class Source(BaseModel):
    organism: Organism | None = None
    mol_type: str | None = Field(None, examples=["genomic DNA"])
    qualifiers: dict[str, list[Qualifier]] | None = None

    model_config = ConfigDict(extra="forbid")


class SourceFeature(BaseModel):
    alias: str | None = None
    location: str | None = Field(None, examples=["1..2277985"])
    source: Source | None = None
    definition: list[str] | None = None

    model_config = ConfigDict(extra="forbid")


class Entry(BaseModel):
    accession: str | None = Field(None, examples=["AB123456.1"])
    alias: str | None = Field(None, examples=["contig_001"])
    name: str | None = None
    type: str | None = Field(None, examples=["chromosome"])
    topology: str | None = Field(None, examples=["circular"])
    sequence: str | None = None
    comments: list[str] | None = None
    source_features: list[SourceFeature] | None = None

    model_config = ConfigDict(extra="forbid")


class StructuredComment(BaseModel):
    tagset_id: str | None = Field(
        None, examples=["Genome-Assembly-Data"]
    )
    fields: dict[str, str] | None = None

    model_config = ConfigDict(extra="forbid")


class Sequences(BaseModel):
    seq_prefix: str | None = Field(None, examples=["contig"])
    common_source: Source | None = None
    entries: list[Entry] | None = None
    structured_comments: list[StructuredComment] | None = None

    model_config = ConfigDict(extra="forbid")


# === Features ===


class Feature(BaseModel):
    alias: str | None = None
    type: str | None = Field(None, examples=["CDS"])
    location: str | None = Field(None, examples=["1..2277985"])
    sequence_id: str | None = None
    qualifiers: dict[str, list[Qualifier]] | None = None
    locus_tag_id: str | None = None
    source_tool: str | None = None
    score: float | None = None

    model_config = ConfigDict(extra="forbid")


# === Assembly ===


class Assembly(BaseModel):
    accession: str | None = Field(None, examples=["GCA_000001405.29"])
    alias: str | None = None
    name: str | None = None
    assembly_level: str | None = Field(None, examples=["contig"])
    genome_representation: str | None = Field(None, examples=["full"])

    model_config = ConfigDict(extra="forbid")


# === Dataset ===


class Dataset(BaseModel):
    accession: str | None = Field(None, examples=["JGAD000001"])
    alias: str | None = None
    title: str | None = None
    description: str | None = None
    dataset_types: list[str] | None = None

    model_config = ConfigDict(extra="forbid")


# === Access Control ===


class Policy(BaseModel):
    accession: str | None = Field(None, examples=["JGAP000001"])
    alias: str | None = None
    title: str | None = None
    policy_text: str | None = None
    policy_url: str | None = None

    model_config = ConfigDict(extra="forbid")


class Dac(BaseModel):
    accession: str | None = Field(None, examples=["JGAC000001"])
    alias: str | None = None
    contacts: list[Person] | None = None

    model_config = ConfigDict(extra="forbid")


class AccessControl(BaseModel):
    policy: Policy | None = None
    dac: Dac | None = None

    model_config = ConfigDict(extra="forbid")


# === Relations ===


class RelationSource(BaseModel):
    type: str | None = Field(None, examples=["sample"])
    alias: str | None = None

    model_config = ConfigDict(extra="forbid")


class RelationTarget(BaseModel):
    url: str | None = None
    db: str | None = Field(None, examples=["biosample"])
    id: str | None = Field(None, examples=["SAMD00123456"])

    model_config = ConfigDict(extra="forbid")


class Relation(BaseModel):
    type: str | None = Field(None, examples=["child_of"])
    source: RelationSource | None = None
    target: RelationTarget | None = None
    label: str | None = None
    properties: dict[str, str] | None = None

    model_config = ConfigDict(extra="forbid")


# === DdbjRecord ===


class DdbjRecord(BaseModel):
    schema_version: str | None = Field(None, examples=["v3.0"])
    provenance: Provenance | None = None
    submission: Submission | None = None
    project: Project | None = None
    samples: list[Sample] | None = None
    experiments: list[Experiment] | None = None
    runs: list[Run] | None = None
    analyses: list[Analysis] | None = None
    sequences: Sequences | None = None
    features: list[Feature] | None = None
    assembly: Assembly | None = None
    datasets: list[Dataset] | None = None
    relations: list[Relation] | None = None
    access_control: AccessControl | None = None

    model_config = ConfigDict(extra="forbid")
