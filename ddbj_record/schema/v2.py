from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ddbj_record.schema import LEGACY_SCHEMA_VERSION_MAP


class Provenance(BaseModel):
    """
    Provenance metadata for a ddbj_record file.
    This class is designed to record the provenance (origin and history) of a ddbj_record file.
    It is intended to capture metadata that is not directly represented elsewhere, such as
    the software used for data conversion, timestamps, and input sources. Each application
    can freely add additional fields as needed, as extra fields are allowed by the model configuration.
    This flexibility ensures that all relevant provenance information can be included to support
    traceability and reproducibility of the dataset.
    """

    source_format: Literal["GFF", "ST26", "TradAnnotation"] | None = Field(
        None,
        examples=["GFF3"],
        description="The original format of the input data, e.g., GFF, ST26, TradAnnotation, etc.",
    )

    # extra field
    model_config = ConfigDict(extra="allow")


# === Submission ===


class Address(BaseModel):
    """
    Postal address of an organization or person.
    """

    country: str = Field(
        ...,
        examples=["Japan"],
        description="The country of the address.",
    )
    state: str | None = Field(
        None,
        examples=["Shizuoka"],
        description="The state or region of the address.",
    )
    city: str = Field(..., examples=["Mishima"], description="The city of the address.")
    street: str | None = Field(
        None,
        examples=["Yata 1111"],
        description="The street address.",
    )
    postal_code: str | None = Field(
        None,
        examples=["411-8540"],
        description="The postal or ZIP code.",
    )

    # extra field
    model_config = ConfigDict(extra="forbid")


class Organization(BaseModel):
    """
    Organization information.
    """

    name: str = Field(
        ...,
        examples=["National Institute of Genetics"],
        description="The full name of the organization.",
    )
    abbreviation: str | None = Field(
        None,
        examples=["NIG"],
        description="The abbreviated name of the organization.",
    )
    url: str | None = Field(
        None,
        examples=["http://www.ddbj.nig.ac.jp"],
        description="The URL of the organization's website.",
    )
    role: str | None = Field(
        None,
        examples=["owner"],
        description="The role of the organization in the submission (e.g., owner, participant). This corresponds to roles in BioProject and BioSample submissions.",
    )
    type: Literal["institution", "company", "government", "non-profit", "consortium", "other"] | None = Field(
        None,
        examples=["institution"],
        description="The type of organization (e.g., institution, company, government, non-profit, consortium, other).",
    )
    department: str | None = Field(
        None,
        examples=["DNA Data Bank of Japan"],
        description="The department within the organization.",
    )
    address: Address | None = Field(None, description="The postal address of the organization.")
    ror_id: str | None = Field(
        None,
        examples=["https://ror.org/01xq5f0"],
        description="The Research Organization Registry (ROR) identifier for the organization.",
    )

    # extra field
    model_config = ConfigDict(extra="forbid")


class Person(BaseModel):
    """
    Individual person information.
    """

    name: str | None = Field(None, examples=["Hanako Mishima"], description="The full name of the person.")
    abbreviation: str | None = Field(
        None,
        examples=["Mishima,H."],
        description="The abbreviated name of the person.",
    )
    email: str | None = Field(
        None,
        examples=["mishima@ddbj.nig.ac.jp"],
        description="The email address of the person.",
    )
    orcid: str | None = Field(
        None,
        examples=["0000-0000-0000-0000"],
        description="The ORCID identifier for the person.",
    )
    organization: list[Organization] | None = Field(
        None,
        description="The organization that the person is affiliated with.",
    )

    # extra field
    model_config = ConfigDict(extra="forbid")


class Xref(BaseModel):
    """
    Cross-reference to external databases.
    This class represents a reference to an entry in an external database,
    including the database name, accession ID, and the relationship type between the current record and the external entry.
    Database names use prefixes from https://registry.identifiers.org/registry.
    """

    db: Literal[
        "bioproject",  # https://registry.identifiers.org/registry/bioproject
        "biosample",  # https://registry.identifiers.org/registry/biosample
        "insdc.sra",  # https://registry.identifiers.org/registry/insdc.sra
        "jga",  # Japanese Genotype-phenotype Archive, https://www.ddbj.nig.ac.jp/jga/index.html
        "gea",  # Genomic Expression Archive, https://www.ddbj.nig.ac.jp/gea/index.html
        "insdc.gca",  # https://registry.identifiers.org/registry/insdc.gca
        "insdc",  # https://registry.identifiers.org/registry/insdc
        "metabobank",  # MetaboBank, https://www.ddbj.nig.ac.jp/metabobank/index.html
        "taxonomy",  # https://registry.identifiers.org/registry/taxonomy
        "geo",  # https://registry.identifiers.org/registry/geo
    ] = Field(
        ...,
        examples=["bioproject"],
        description="The name of the external database using prefixes from https://registry.identifiers.org/registry where available.",
    )
    id: str = Field(
        ...,
        examples=["PRJDB999999"],
        description="The accession number or identifier in the external database.",
    )

    # extra field
    model_config = ConfigDict(extra="forbid")


class Reference(BaseModel):
    """
    Bibliographic reference information.
    This class represents a scientific publication or reference associated with the data,
    including title, authors, publication status, journal information, and identifiers.
    """

    title: str = Field(
        ...,
        examples=["Sequence and analysis of mouse ch.8"],
        description="The title of the publication or reference.",
    )
    authors: list[Person] = Field(
        default_factory=list,
        description="The list of authors who contributed to the publication.",
    )
    consortiums: list[Organization] | None = Field(
        None,
        description="The list of consortium organizations involved in the publication.",
    )
    status: Literal["unpublished", "in-press", "published"] = Field(
        ...,
        examples=["unpublished"],
        description="The publication status of the reference.",
    )
    year: str = Field(
        ...,
        examples=["2025"],
        description="The year of publication.",
    )
    journal: str | None = Field(
        None,
        examples=["Nature"],
        description="The name of the journal where the article was published.",
    )
    volume: str | None = Field(
        None,
        examples=["8"],
        description="The volume number of the journal.",
    )
    issue: str | None = Field(
        None,
        examples=["1"],
        description="The issue number of the journal.",
    )
    start_page: str | None = Field(
        None,
        examples=["15"],
        description="The starting page number of the article.",
    )
    end_page: str | None = Field(
        None,
        examples=["20"],
        description="The ending page number of the article.",
    )
    date_published: str | None = Field(
        None,
        examples=["2025-01-01"],
        description="The date when the article was published (ISO 8601 format).",
    )
    doi: str | None = Field(
        None,
        examples=["10.1038/nature12345"],
        description="The Digital Object Identifier (DOI) of the publication.",
    )
    url: str | None = Field(
        None,
        examples=["https://doi.org/10.1038/nature12345"],
        description="The URL of the publication.",
    )
    pubmed_id: str | None = Field(
        None,
        examples=["12345678"],
        description="The PubMed identifier of the publication.",
    )

    # extra field
    model_config = ConfigDict(extra="forbid")


class Submission(BaseModel):
    """
    Submission metadata for data deposit to DDBJ.
    This class contains information about the submitters, cross-references to external databases,
    publication references, and submission-specific parameters such as data type and hold date.
    """

    submitters: list[Person] = Field(
        default_factory=list,
        description="The list of people who are submitting the data.",
    )
    db_xrefs: list[Xref] = Field(
        default_factory=list,
        description="Cross-references to external databases related to this submission.",
    )
    references: list[Reference] = Field(
        default_factory=list,
        description="List of publications or references associated with this submission.",
    )
    comments: list[list[str]] = Field(
        default_factory=list,
        examples=[["Example comment line 1", "Annotated by DFAST"]],
        description="Additional comments or notes about the submission.",
    )

    # TODO: These fields originated from GenBank format and are used by DFAST.
    # They require more structured enumeration, but the original definitions need further clarification.
    trad_submission_category: str | None = Field(
        None,
        examples=["WGS"],
        description="Traditional submission category. If the submission is a draft genome, the value is 'WGS', and if it is a complete genome, the value is 'GNM'.",
    )
    division: str | None = Field(
        None,
        examples=["BCT"],
        description="The GenBank division code for the submission.",
    )
    locus_tag_prefix: str | None = Field(
        None,
        examples=["PLH"],
        description="The prefix used for locus tags in the submission.",
    )
    seq_prefix: str | None = Field(
        None,
        examples=["sequence", "contig"],
        description="Prefix for sequence names. It is used when the data is WGS.",
    )
    hold_date: str | None = Field(
        None,
        examples=["2025-01-01"],
        description="The date until which the submission should be held before public release (ISO 8601 format).",
    )

    # extra field
    model_config = ConfigDict(extra="forbid")


# === Experiment (JGA experiment schema subset) ===


class LibraryLayout(BaseModel):
    """
    LIBRARY_LAYOUT specifies whether to expect single, paired, or other configuration of reads.
    """

    layout_type: Literal["SINGLE", "PAIRED"] = Field(
        ...,
        examples=["PAIRED"],
        description="Specifies whether to expect single or paired reads.",
    )
    nominal_length: int | None = Field(
        None,
        examples=[300],
        description="Expected insert size for paired reads.",
    )
    nominal_sdev: float | None = Field(
        None,
        examples=[50.0],
        description="Standard deviation of the insert size for paired reads.",
    )

    # extra field
    model_config = ConfigDict(extra="forbid")


class TargetedLocus(BaseModel):
    """
    TARGETED_LOCI from JGA experiment schema.
    """

    locus_name: Literal["16S rRNA", "18S rRNA", "RBCL", "matK", "COX1", "ITS1-5.8S-ITS2", "exome", "other"] = Field(
        ...,
        examples=["16S rRNA"],
        description="The name of the targeted locus.",
    )
    description: str | None = Field(
        None,
        description="Submitter supplied description of alternate locus and auxiliary information.",
    )

    # extra field
    model_config = ConfigDict(extra="forbid")


class Design(BaseModel):
    """
    DESIGN element from JGA experiment schema (LibraryType).
    """

    design_description: str | None = Field(
        None,
        description="Goal and setup of the individual library.",
    )
    library_name: str | None = Field(
        None,
        examples=["lib1"],
        description="The submitter's name for this library.",  # from JGA experiment schema
    )
    library_strategy: (
        Literal[
            # From SEQUENCING_LIBRARY_STRATEGY
            "WGS",
            "WGA",
            "WXS",
            "RNA-Seq",
            "ssRNA-seq",
            "miRNA-Seq",
            "ncRNA-Seq",
            "WCS",
            "RAD-Seq",
            "CLONE",
            "POOLCLONE",
            "AMPLICON",
            "CLONEEND",
            "FINISHING",
            "ChIP-Seq",
            "MNase-Seq",
            "DNase-Hypersensitivity",
            "Bisulfite-Seq",
            "EST",
            "Hi-C",
            "ATAC-seq",
            "FL-cDNA",
            "CTS",
            "MRE-Seq",
            "MeDIP-Seq",
            "MBD-Seq",
            "Tn-Seq",
            "VALIDATION",
            "FAIRE-seq",
            "SELEX",
            "NOMe-Seq",
            "RIP-Seq",
            "ChIA-PET",
            "Synthetic-Long-Read",
            "Targeted-Capture",
            "Tethered Chromatin Conformation Capture",
            "OTHER",
            # From ARRAY_LIBRARY_STRATEGY
            "Genotyping by array",
            "Transcription profiling by array",
            "microRNA profiling by array",
            "ChIP-chip by array",
        ]
        | None
    ) = Field(
        None,
        examples=["RNA-Seq"],
        description="Sequencing technique intended for this library.",
    )
    library_source: (
        Literal[
            "GENOMIC",
            "GENOMIC SINGLE CELL",
            "TRANSCRIPTOMIC",
            "TRANSCRIPTOMIC SINGLE CELL",
            "METAGENOMIC",
            "METATRANSCRIPTOMIC",
            "SYNTHETIC",
            "VIRAL RNA",
            "OTHER",
        ]
        | None
    ) = Field(
        None,
        examples=["TRANSCRIPTOMIC"],
        description="The type of source material that is being sequenced.",
    )
    library_selection: (
        Literal[
            "RANDOM",
            "PCR",
            "RANDOM PCR",
            "RT-PCR",
            "HMPR",
            "MF",
            "repeat fractionation",
            "size fractionation",
            "MSLL",
            "cDNA",
            "cDNA_randomPriming",
            "cDNA_oligo_dT",
            "PolyA",
            "Oligo-dT",
            "Inverse rRNA",
            "ChIP",
            "MNase",
            "DNase",
            "Hybrid Selection",
            "Reduced Representation",
            "DNA shearing",
            "Restriction Digest",
            "5-methylcytidine antibody",
            "MBD2 protein methyl-CpG binding domain",
            "CAGE",
            "RACE",
            "MDA",
            "padlock probes capture method",
            "other",
            "unspecified",
        ]
        | None
    ) = Field(
        None,
        examples=["PolyA"],
        description="Method used to enrich the target in the sequence library preparation.",
    )
    library_layout: LibraryLayout | None = Field(
        None,
        description="Specifies whether to expect single, paired, or other configuration of reads.",
    )

    # === Optional? ===
    targeted_loci: list[TargetedLocus] | None = Field(
        None,
        description="Names the gene(s) or locus(loci) or other genomic feature(s) targeted by the sequence.",
    )
    pooling_strategy: str | None = Field(
        None,
        description="The optional pooling strategy indicates how the library or libraries are organized if multiple samples are involved.",
    )
    library_construction_protocol: str | None = Field(
        None,
        description="Free form text describing the protocol by which the sequencing library was constructed.",
    )

    # extra field
    model_config = ConfigDict(extra="forbid")


class Platform(BaseModel):
    """
    PLATFORM element from JGA experiment schema.
    Simplified to just store platform information as strings.
    """

    platform_type: str | None = Field(
        None,
        examples=["ILLUMINA"],
        description="The type of platform used (sequencing or array).",
    )
    instrument_model: str | None = Field(
        None,
        examples=["Illumina HiSeq 2500"],
        description="The specific instrument model used.",
    )

    # extra field
    model_config = ConfigDict(extra="forbid")


class Experiment(BaseModel):
    """
    Experiment element from JGA experiment schema (subset).
    An Experiment specifies what will be sequenced and how the sequencing will be performed.
    """

    id: str = Field(
        ...,
        examples=["exp1"],
        description="The unique identifier for this experiment.",
    )
    title: str | None = Field(
        None,
        examples=["RNA-seq experiment"],
        description="Short text that can be used to call out experiment records in searches or displays.",
    )
    design: Design | None = Field(
        None,
        description="Library design information.",
    )
    platform: Platform | None = Field(
        None,
        description="The sequencing or array platform information.",
    )
    experiment_attributes: dict[str, str] = Field(
        default_factory=dict,
        examples=[{"assembly_method": "HGAP v. x.x", "genome_coverage": "60x"}],
        description="Experiment attributes as key-value pairs. This is a simplified version of EXPERIMENT_ATTRIBUTES, where each attribute is represented as a key-value pair.",
    )

    # extra field
    model_config = ConfigDict(extra="forbid")


# === Sequences ===


class Qualifier(BaseModel):
    """
    Qualifier information for sequence features.
    This class represents key-value pairs that provide additional information about sequence features,
    such as gene names, product descriptions, or other annotations.
    """

    id: str | None = Field(
        None,
        examples=["qualifier_1"],
        description="The unique identifier for this qualifier.",
    )
    value: str = Field(
        ...,
        examples=["Paucilactobacillus hokkaidonensis", "genomic DNA", "1", "true"],
        description="""\
        The value of the qualifier.
        Can be text, numbers, or boolean-like values. All values are represented as strings.
        For qualifiers with 'none' value_format (e.g., circular_RNA which appears as '/circular_RNA' without a value), this field stores 'true' when the qualifier is present.
        """,
    )

    # extra field
    model_config = ConfigDict(extra="forbid")


class Source(BaseModel):
    """
    INSDC source feature information.
    This class represents the source feature in INSDC feature tables, which describes
    the biological source of the sequence including organism and molecule type.
    """

    organism: str = Field(
        ...,
        examples=["Paucilactobacillus hokkaidonensis"],
        description="The scientific name or higher-level classification of the organism or agent that provided the sequenced genetic material.",
    )
    mol_type: str = Field(
        ...,
        examples=["genomic DNA"],
        description="The type of molecule sequenced",
    )  # mol_type are defined in INSDC specifications, but enumerating them would require schema updates every time they change, so we intentionally avoid enumeration here.
    qualifiers: dict[str, list[Qualifier]] = Field(
        default_factory=dict,
        description="Additional qualifiers. Key is the qualifier name.",
    )

    # extra field
    model_config = ConfigDict(extra="forbid")


class SourceFeature(BaseModel):
    """
    Class representing the source feature itself.
    These pieces of information are not written directly to Entry but held as List[SourceFeature]
    because multiple source features can exist in a sequence entry.
    """

    id: str = Field(
        ...,
        examples=["feature_8"],
        description="The unique identifier for this source feature.",
    )
    location: str = Field(
        ...,
        examples=["1..2277985"],
        description="The location range of the sequence in INSDC format.",
    )
    source: Source | None = Field(
        None,
        description="Optional source information specific to this entry. When specified, this overrides the common_source.",
    )
    definition: list[str] | None = Field(
        None,
        description="Definition lines for the sequence entry. This field contains the content of ff_definition as-is.",
    )


class Entry(BaseModel):
    """
    Individual sequence entry information.
    This class represents a single sequence entry with its metadata.
    Each entry can have its own source information that overrides the common source when specified.
    """

    id: str = Field(
        ...,
        examples=["chromosome"],
        description="The unique identifier for this sequence entry, typically used as FASTA header ID or submitter sequence ID.",
    )
    name: str = Field(
        ...,
        examples=["chromosome"],
        description="The user-specified name of the sequence (e.g., contig1, contig2, etc. for draft genomes).",
    )
    type: Literal["chromosome", "plasmid", "unplaced", "other"] = Field(
        ...,
        examples=["chromosome"],
        description="The type of the sequence (e.g., chromosome, plasmid, unplaced, other).",
    )
    topology: Literal["circular", "linear"] = Field(
        ...,
        examples=["circular"],
        description="The topology of the sequence (circular or linear).",
    )
    sequence: str | None = Field(
        None,
        examples=["atgc..."],
        description="The nucleotide sequence data. Optional field that may be omitted for large sequences.",
    )
    comments: list[list[str]] | None = Field(
        None,
        description="Comments specific to this entry.",
    )
    source_features: list[SourceFeature] = Field(
        default_factory=list,
        description="List of source features associated with this entry. Multiple source features can exist in a single entry.",
    )

    # extra field
    model_config = ConfigDict(extra="forbid")


class Sequences(BaseModel):
    """
    Collection of sequence entries with common source information.
    This class contains a common source that applies to all entries unless overridden
    by individual entry-specific source information.
    """

    common_source: Source = Field(
        ...,
        description="The common source information that applies to all sequence entries unless overridden by individual entry sources.",
    )
    entries: list[Entry] = Field(
        default_factory=list,
        description="List of individual sequence entries, each with its own metadata and optional sequence data.",
    )

    # extra field
    model_config = ConfigDict(extra="forbid")


# === Feature ===


class Feature(BaseModel):
    """
    INSDC feature annotation information.
    This class represents a single feature annotation on a sequence, including its type,
    location, and associated qualifiers that provide detailed biological information.
    """

    id: str = Field(
        ...,
        examples=["feature_8"],
        description="The unique identifier for this feature.",
    )
    type: str = Field(
        ...,
        examples=["CDS"],
        description="The type of the feature (e.g., CDS, gene, rRNA, tRNA).",
    )  # Feature types are defined in INSDC specifications, but enumerating them would require schema updates every time they change, so we intentionally avoid enumeration here.
    location: str = Field(
        ...,
        examples=["1..2277985"],
        description="The location of the feature on the sequence in INSDC format.",
    )
    sequence_id: str = Field(
        ...,
        examples=["chromosome"],
        description="The ID of the sequence entry to which this feature belongs.",
    )
    qualifiers: dict[str, list[Qualifier]] = Field(
        default_factory=dict,
        description="Qualifiers that provide additional information about this feature. Key is the qualifier name.",
    )
    locus_tag_id: str | None = Field(
        None,
        examples=["00010"],
        description="The locus tag identifier associated with this feature, if applicable. The source feature does not have a locus tag and this field.",
    )

    # extra field
    model_config = ConfigDict(extra="forbid")


# === DDBJ Record ===


class DdbjRecord(BaseModel):
    """
    Complete DDBJ record structure.
    This is the root class that contains all information for a DDBJ data submission,
    including metadata, sequences, features, and experimental information.
    """

    schema_version: str = Field(
        ...,
        examples=["v2.0"],
        description="The version of the DDBJ record schema used for this data.",
    )

    @field_validator("schema_version", mode="before")
    @classmethod
    def normalize_schema_version(cls, v: str) -> str:
        return LEGACY_SCHEMA_VERSION_MAP.get(v, v)

    provenance: Provenance = Field(
        ...,
        description="Metadata that records the origin and transformation history of the data, including conversion software, timestamps, and input sources.",
    )
    submission: Submission = Field(
        ...,
        description="Submission metadata including submitters, cross-references, and submission parameters.",
    )
    experiments: list[Experiment] = Field(
        default_factory=list,
        description="List of experimental information associated with this submission.",
    )
    sequences: Sequences = Field(
        ...,
        description="Collection of sequence entries with their metadata and optional sequence data.",
    )
    features: list[Feature] = Field(
        default_factory=list,
        description="List of feature annotations associated with the sequences.",
    )

    # extra field
    model_config = ConfigDict(extra="forbid")
