from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# === Common types ===


class Organism(BaseModel):
    name: str | None = Field(None, examples=["Homo sapiens"])
    common_name: str | None = Field(None, examples=["human"])
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


class Attribute(BaseModel):
    # 名前は必須で、空白だけも不可。名前の無い属性は何の値かが分からず検証しようが
    # ない。正規化で前後の空白を落とすので、`"  "` も名前が無いのと同じになる。
    name: str = Field(pattern=r"\S", examples=["collection_date"])
    value: str | None = None
    unit: str | None = None

    model_config = ConfigDict(extra="forbid")


class Identifier(BaseModel):
    """accession 以外の識別子(SRA IDENTIFIERS)。

    type は "primary" / "secondary" / "external" / "submitter" / "uuid"。
    namespace は external / submitter が持つ(例: "BioSample", "NGDC")。
    """

    type: str | None = Field(None, examples=["secondary"])
    value: str | None = Field(None, examples=["SRS000001"])
    label: str | None = None
    namespace: str | None = Field(None, examples=["BioSample"])

    model_config = ConfigDict(extra="forbid")


class ExternalRef(BaseModel):
    """record の中に埋め込まれた、URL か DB の項目への参照。

    record のオブジェクトの間の関係は relations に置く。これはその関係の一部では
    なく、ある値そのものが外部の何かを指しているときに使う(参照アセンブリの名前、
    targeted locus のプローブなど)。
    """

    url: str | None = None
    db: str | None = Field(None, examples=["GenBank"])
    id: str | None = Field(None, examples=["NC_000001.11"])
    label: str | None = None

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


# === ST.26 ===


class InventionTitle(BaseModel):
    title: str | None = None
    language_code: str | None = Field(None, examples=["ja"])

    model_config = ConfigDict(extra="forbid")


class ApplicationIdentification(BaseModel):
    ip_office_code: str | None = Field(None, examples=["JP"])
    application_number_text: str | None = None
    filing_date: str | None = Field(None, examples=["2024-01-15"])

    model_config = ConfigDict(extra="forbid")


class St26Meta(BaseModel):
    dtd_version: str | None = Field(None, examples=["V1_3"])
    software_name: str | None = None
    software_version: str | None = None
    production_date: str | None = None
    original_language: str | None = Field(None, examples=["ja"])
    non_english_language: str | None = Field(None, examples=["ja"])
    applicant_file_reference: str | None = None
    application: ApplicationIdentification | None = None
    earliest_priority: ApplicationIdentification | None = None
    applicant_name: str | None = None
    applicant_name_latin: str | None = None
    inventor_name: str | None = None
    inventor_name_latin: str | None = None
    invention_titles: list[InventionTitle] | None = None

    model_config = ConfigDict(extra="forbid")


# === Submission ===


class SraContact(BaseModel):
    """SRA SUBMISSION/CONTACTS/CONTACT。登録の経過を知らせる宛先。"""

    name: str | None = None
    inform_on_status: str | None = Field(None, examples=["mishima@ddbj.nig.ac.jp"])
    inform_on_error: str | None = Field(None, examples=["mishima@ddbj.nig.ac.jp"])

    model_config = ConfigDict(extra="forbid")


class SraActionLegacy(BaseModel):
    """SRA XSD 1.5 より前の ACTION にだけある属性。"""

    hold_for_period: str | None = None
    notes: str | None = None

    model_config = ConfigDict(extra="forbid")


class SraAction(BaseModel):
    """SRA SUBMISSION/ACTIONS/ACTION の 1 つ。書かれた順に並べる。

    type は ACTION の子要素の名前("ADD" / "MODIFY" / "VALIDATE" / "HOLD" /
    "RELEASE" / "SUPPRESS" / "PROTECT")。object_type は @schema の値そのまま。
    """

    type: str | None = Field(None, examples=["ADD"])
    source: str | None = Field(None, examples=["DRA000001.experiment.xml"])
    object_type: str | None = Field(None, examples=["experiment"])
    target: str | None = None
    hold_until_date: str | None = Field(None, examples=["2025-01-01"])
    legacy: SraActionLegacy | None = None

    model_config = ConfigDict(extra="forbid")


class SraSubmissionLegacy(BaseModel):
    """SRA XSD 1.5 より前の SUBMISSION にだけある要素と属性。"""

    submission_id: str | None = None
    files: list[File] | None = None

    model_config = ConfigDict(extra="forbid")


class SraSubmission(BaseModel):
    """SRA の SUBMISSION が持つ、登録の手続きについての情報。"""

    lab_name: str | None = None
    submission_date: str | None = None
    submission_comment: str | None = None
    contacts: list[SraContact] | None = None
    actions: list[SraAction] | None = None
    legacy: SraSubmissionLegacy | None = None

    model_config = ConfigDict(extra="forbid")


class Submission(BaseModel):
    accession: str | None = Field(None, examples=["DRA000001"])
    alias: str | None = None
    title: str | None = None
    submitters: list[Person] | None = None
    hold_date: str | None = Field(None, examples=["2025-01-01"])
    comments: list[str] | None = None
    st26: St26Meta | None = None
    sra: SraSubmission | None = None
    attributes: list[Attribute] | None = None
    identifiers: list[Identifier] | None = None
    center_name: str | None = Field(None, examples=["NIG"])
    broker_name: str | None = None

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
    consortiums: list[str] | None = None

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


class ProjectLegacy(BaseModel):
    """SRA XSD 1.5 より前の STUDY にだけある要素。"""

    # DESCRIPTOR/PROJECT_ID(NCBI Genome Project の番号)
    project_id: str | None = None

    model_config = ConfigDict(extra="forbid")


class Project(BaseModel):
    accession: str | None = Field(None, examples=["PRJDB12345"])
    alias: str | None = None
    name: str | None = None
    title: str | None = None
    description: str | None = None
    project_type: str | None = Field(None, examples=["primary"])
    umbrella_subtype: str | None = Field(
        None, examples=["eComparativeGenomics"]
    )
    study_types: list[str] | None = None
    organism: Organism | None = None
    publications: list[Publication] | None = None
    grants: list[Grant] | None = None
    keywords: list[str] | None = None
    relevance: dict[str, str] | None = None
    locus_tag_prefix: list[str] | None = None
    target: ProjectTarget | None = None
    attributes: list[Attribute] | None = None
    identifiers: list[Identifier] | None = None
    center_name: str | None = None
    broker_name: str | None = None
    # SRA STUDY の DESCRIPTOR。description は STUDY_ABSTRACT を持つ。
    study_description: str | None = None
    center_project_name: str | None = None
    # SRA XSD 1.5d2 の DESCRIPTOR/CENTER_NAME。STUDY@center_name とは別の要素。
    descriptor_center_name: str | None = None
    # STUDY_TYPE@new_study_type。XSD は existing_study_type が "Other" のときに使うと説明する。
    new_study_type: str | None = None
    legacy: ProjectLegacy | None = None

    model_config = ConfigDict(extra="forbid")


# === Sample ===


class Sample(BaseModel):
    accession: str | None = Field(None, examples=["SAMD00123456"])
    alias: str | None = None
    title: str | None = None
    description: str | None = None
    organism: Organism | None = None
    attributes: list[Attribute] | None = None
    package: str | None = Field(None, examples=["MIGS.ba"])
    donor_id: str | None = None
    sample_group_type: str | None = Field(None, examples=["case"])
    identifiers: list[Identifier] | None = None
    center_name: str | None = None
    broker_name: str | None = None
    # SRA SAMPLE_NAME。個人を特定しない名前と、個体の名前。
    anonymized_name: str | None = None
    individual_name: str | None = None

    model_config = ConfigDict(extra="forbid")


# === Experiment ===


class LibraryLegacy(BaseModel):
    """SRA XSD 1.5 より前の LIBRARY_DESCRIPTOR にだけある属性。"""

    # LIBRARY_LAYOUT/PAIRED@ORIENTATION
    orientation: str | None = Field(None, examples=["5'-3'-3'-5'"])

    model_config = ConfigDict(extra="forbid")


class LibraryDescriptor(BaseModel):
    name: str | None = None
    strategy: str | None = Field(None, examples=["WGS"])
    source: str | None = Field(None, examples=["GENOMIC"])
    selection: str | None = Field(None, examples=["RANDOM"])
    layout: str | None = Field(None, examples=["paired"])
    nominal_length: int | None = None
    nominal_sdev: float | None = None
    construction_protocol: str | None = None
    pooling_strategy: str | None = None
    legacy: LibraryLegacy | None = None

    model_config = ConfigDict(extra="forbid")


class TargetedLocus(BaseModel):
    name: str | None = Field(None, examples=["16S rRNA"])
    description: str | None = None
    probe_set: ExternalRef | None = None

    model_config = ConfigDict(extra="forbid")


class ColorMatrixEntry(BaseModel):
    """SOLiD の 2 塩基と色の対応(ABI_SOLID/COLOR_MATRIX/COLOR)。"""

    dibase: str | None = Field(None, examples=["AC"])
    color: str | None = Field(None, examples=["1"])

    model_config = ConfigDict(extra="forbid")


class PlatformLegacy(BaseModel):
    """SRA XSD 1.5 より前の PLATFORM にだけある、装置ごとの運転条件。"""

    cycle_count: int | None = None
    sequence_length: int | None = None
    cycle_sequence: str | None = None
    flow_count: int | None = None
    flow_sequence: str | None = None
    key_sequence: str | None = None
    color_matrix: list[ColorMatrixEntry] | None = None
    color_matrix_code: str | None = None

    model_config = ConfigDict(extra="forbid")


class Platform(BaseModel):
    type: str | None = Field(None, examples=["ILLUMINA"])
    instrument_model: str | None = Field(
        None, examples=["Illumina HiSeq 2500"]
    )
    array_name: str | None = None
    array_description: str | None = None
    array_provider: str | None = None
    legacy: PlatformLegacy | None = None

    model_config = ConfigDict(extra="forbid")


class RelativeOrder(BaseModel):
    follows_read_index: int | None = None
    precedes_read_index: int | None = None

    model_config = ConfigDict(extra="forbid")


class Basecall(BaseModel):
    """EXPECTED_BASECALL_TABLE の 1 行。バーコードなど、その位置に来るはずの配列。"""

    value: str | None = Field(None, examples=["ACGTACGT"])
    read_group_tag: str | None = None
    min_match: int | None = None
    max_mismatch: int | None = None
    match_edge: str | None = Field(None, examples=["start"])

    model_config = ConfigDict(extra="forbid")


class BasecallTable(BaseModel):
    base_coord: int | None = None
    default_length: int | None = None
    basecalls: list[Basecall] | None = None

    model_config = ConfigDict(extra="forbid")


class ExpectedBasecall(BaseModel):
    """READ_SPEC/EXPECTED_BASECALL。表でなく 1 つの配列を書く。"""

    value: str | None = Field(None, examples=["TCAG"])
    base_coord: int | None = None
    default_length: int | None = None

    model_config = ConfigDict(extra="forbid")


class ReadSpecLegacy(BaseModel):
    """SRA XSD 1.5 より前の、READ_SPEC の位置の決め方。"""

    cycle_coord: int | None = None
    expected_basecall: ExpectedBasecall | None = None

    model_config = ConfigDict(extra="forbid")


class ReadSpec(BaseModel):
    read_index: int | None = None
    read_label: str | None = None
    read_class: str | None = Field(
        None, examples=["Application Read"]
    )
    read_type: str | None = Field(None, examples=["Forward"])
    # 読みの位置は次の 3 つ(1.5 より前は legacy の 2 つを加えた 5 つ)のどれか 1 つで決める。
    base_coord: int | None = None
    relative_order: RelativeOrder | None = None
    expected_basecall_table: BasecallTable | None = None
    legacy: ReadSpecLegacy | None = None

    model_config = ConfigDict(extra="forbid")


class SpotDescriptorLegacy(BaseModel):
    """SRA XSD 1.5 より前の SPOT_DECODE_SPEC にだけある要素。"""

    number_of_reads_per_spot: int | None = None
    adapter_spec: str | None = None

    model_config = ConfigDict(extra="forbid")


class SpotDescriptor(BaseModel):
    spot_length: int | None = None
    reads: list[ReadSpec] | None = None
    legacy: SpotDescriptorLegacy | None = None

    model_config = ConfigDict(extra="forbid")


class PipelineStep(BaseModel):
    step_index: str | None = None
    prev_step_indexes: list[str] | None = None
    program: str | None = None
    version: str | None = None
    section_name: str | None = None
    notes: str | None = None

    model_config = ConfigDict(extra="forbid")


class Gap(BaseModel):
    """DESIGN/GAP_DESCRIPTOR/GAP。

    type は GAP_TYPE の子要素の名前("MatePair" / "PairedEnd" / "Tandem")。
    """

    type: str | None = Field(None, examples=["PairedEnd"])
    orientation: str | None = None
    link5: str | None = Field(None, examples=["R3"])
    link3: str | None = Field(None, examples=["F3"])
    min_length: int | None = None
    max_length: int | None = None
    mean: float | None = None
    stdev: float | None = None

    model_config = ConfigDict(extra="forbid")


class BaseCalling(BaseModel):
    """PROCESSING/BASE_CALLS。"""

    base_caller: str | None = None
    sequence_space: str | None = Field(None, examples=["Base Space"])

    model_config = ConfigDict(extra="forbid")


class QualityScoring(BaseModel):
    """PROCESSING/QUALITY_SCORES。"""

    qtype: str | None = Field(None, examples=["phred"])
    quality_scorer: str | None = None
    number_of_levels: int | None = None
    multiplier: float | None = None

    model_config = ConfigDict(extra="forbid")


class ExperimentLegacy(BaseModel):
    """SRA XSD 1.5 より前の EXPERIMENT にだけある要素と属性。"""

    expected_number_runs: int | None = None
    gaps: list[Gap] | None = None
    base_calling: BaseCalling | None = None
    quality_scoring: list[QualityScoring] | None = None

    model_config = ConfigDict(extra="forbid")


class ReadLabel(BaseModel):
    value: str | None = None
    read_group_tag: str | None = None

    model_config = ConfigDict(extra="forbid")


class PoolMember(BaseModel):
    """1 つの experiment に混ぜた sample の 1 つ(SRA SAMPLE_DESCRIPTOR/POOL)。

    member_name は run の data_blocks[].member_name から指される。
    """

    sample: RelationTarget | None = None
    member_name: str | None = None
    proportion: float | None = None
    read_labels: list[ReadLabel] | None = None

    model_config = ConfigDict(extra="forbid")


class Pool(BaseModel):
    default_member: PoolMember | None = None
    members: list[PoolMember] | None = None

    model_config = ConfigDict(extra="forbid")


class Experiment(BaseModel):
    accession: str | None = Field(None, examples=["DRX000001"])
    alias: str | None = None
    title: str | None = None
    description: str | None = None
    library: LibraryDescriptor | None = None
    platform: Platform | None = None
    targeted_loci: list[TargetedLocus] | None = None
    spot_descriptor: SpotDescriptor | None = None
    processing: list[PipelineStep] | None = None
    attributes: list[Attribute] | None = None
    identifiers: list[Identifier] | None = None
    center_name: str | None = None
    broker_name: str | None = None
    pool: Pool | None = None
    sample_demux_directive: str | None = Field(None, examples=["leave_as_pool"])
    legacy: ExperimentLegacy | None = None

    model_config = ConfigDict(extra="forbid")


# === Run ===


class FileLegacy(BaseModel):
    """SRA XSD 1.5 より前の FILE にだけある要素。"""

    data_series_labels: list[str] | None = None

    model_config = ConfigDict(extra="forbid")


class File(BaseModel):
    filename: str | None = None
    filetype: str | None = Field(None, examples=["fastq"])
    checksum_method: str | None = Field(None, examples=["MD5"])
    checksum: str | None = None
    unencrypted_checksum: str | None = None
    # fastq の品質値の読み方。SRA 形式への変換に要る。
    quality_scoring_system: str | None = Field(None, examples=["phred"])
    quality_encoding: str | None = Field(None, examples=["ascii"])
    ascii_offset: str | None = Field(None, examples=["!"])
    read_labels: list[str] | None = None
    legacy: FileLegacy | None = None

    model_config = ConfigDict(extra="forbid")


class DataBlockLegacy(BaseModel):
    """SRA XSD 1.5 より前の DATA_BLOCK にだけある、装置上の位置と読みの数。"""

    sector: int | None = None
    region: int | None = None
    format_code: int | None = None
    number_channels: int | None = None
    total_spots: int | None = None
    total_reads: int | None = None

    model_config = ConfigDict(extra="forbid")


class DataBlock(BaseModel):
    """files をまとめる単位(SRA / JGA の DATA_BLOCK)。

    member_name は experiment の pool.members[].member_name を指す。
    """

    name: str | None = None
    serial: int | None = None
    member_name: str | None = None
    files: list[File] | None = None
    legacy: DataBlockLegacy | None = None

    model_config = ConfigDict(extra="forbid")


class RunLegacy(BaseModel):
    """SRA XSD 1.5 より前の RUN にだけある属性。

    instrument_model は RUN の属性で、PLATFORM の INSTRUMENT_MODEL とは別に書かれる。
    """

    instrument_model: str | None = None
    instrument_name: str | None = None
    run_file: str | None = None
    total_data_blocks: int | None = None

    model_config = ConfigDict(extra="forbid")


class Run(BaseModel):
    accession: str | None = Field(None, examples=["DRR000001"])
    alias: str | None = None
    title: str | None = None
    run_date: str | None = None
    data_type: str | None = Field(None, examples=["sequencing"])
    data_blocks: list[DataBlock] | None = None
    attributes: list[Attribute] | None = None
    identifiers: list[Identifier] | None = None
    center_name: str | None = None
    broker_name: str | None = None
    run_center: str | None = None
    # experiment の値をこの run に限って上書きするもの。
    platform: Platform | None = None
    spot_descriptor: SpotDescriptor | None = None
    processing: list[PipelineStep] | None = None
    sample_demux_directive: str | None = None
    legacy: RunLegacy | None = None

    model_config = ConfigDict(extra="forbid")


# === Analysis ===


class StandardAssembly(BaseModel):
    short_name: str | None = Field(None, examples=["GRCh38"])
    names: list[ExternalRef] | None = None

    model_config = ConfigDict(extra="forbid")


class CustomAssembly(BaseModel):
    description: str | None = None
    sources: list[ExternalRef] | None = None

    model_config = ConfigDict(extra="forbid")


class RunLabel(BaseModel):
    """アラインメントの read group と、それが来た run の対応。"""

    run: RelationTarget | None = None
    data_block_name: str | None = None
    read_group_label: str | None = None

    model_config = ConfigDict(extra="forbid")


class SeqLabel(BaseModel):
    """アラインメントの参照配列の名前と、その配列の対応。"""

    accession: str | None = Field(None, examples=["NC_000001.11"])
    gi: str | None = None
    data_block_name: str | None = None
    seq_label: str | None = Field(None, examples=["chr1"])

    model_config = ConfigDict(extra="forbid")


class ReferenceAlignment(BaseModel):
    """ANALYSIS_TYPE/REFERENCE_ALIGNMENT。

    run_labels と seq_labels はアラインメントの中の名前(read group と参照配列)を
    外の run や配列と結ぶ表で、analysis というオブジェクトについての関係ではない。
    """

    standard_assembly: StandardAssembly | None = None
    custom_assembly: CustomAssembly | None = None
    run_labels: list[RunLabel] | None = None
    seq_labels: list[SeqLabel] | None = None
    includes_unaligned_reads: bool | None = None
    marks_duplicate_reads: bool | None = None
    includes_failed_reads: bool | None = None

    model_config = ConfigDict(extra="forbid")


class Analysis(BaseModel):
    accession: str | None = Field(None, examples=["DRZ000001"])
    alias: str | None = None
    title: str | None = None
    description: str | None = None
    analysis_type: str | None = Field(
        None, examples=["de_novo_assembly"]
    )
    analysis_date: str | None = None
    data_blocks: list[DataBlock] | None = None
    processing: list[PipelineStep] | None = None
    attributes: list[Attribute] | None = None
    identifiers: list[Identifier] | None = None
    center_name: str | None = None
    broker_name: str | None = None
    analysis_center: str | None = None
    reference_alignment: ReferenceAlignment | None = None

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
    division: str | None = Field(None, examples=["BCT"])
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
    attributes: list[Attribute] | None = None

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
    phase: int | None = None
    parent_ids: list[str] | None = None

    model_config = ConfigDict(extra="forbid")


# === Assembly ===


class Assembly(BaseModel):
    accession: str | None = Field(None, examples=["GCA_000001405.29"])
    alias: str | None = None
    title: str | None = None
    name: str | None = None
    description: str | None = None
    assembly_level: str | None = Field(None, examples=["contig"])
    genome_representation: str | None = Field(None, examples=["full"])
    attributes: list[Attribute] | None = None

    model_config = ConfigDict(extra="forbid")


# === Dataset ===


class Dataset(BaseModel):
    accession: str | None = Field(None, examples=["JGAD000001"])
    alias: str | None = None
    title: str | None = None
    description: str | None = None
    dataset_types: list[str] | None = None
    attributes: list[Attribute] | None = None

    model_config = ConfigDict(extra="forbid")


# === Access Control ===


class Policy(BaseModel):
    accession: str | None = Field(None, examples=["JGAP000001"])
    alias: str | None = None
    title: str | None = None
    policy_text: str | None = None
    policy_url: str | None = None
    attributes: list[Attribute] | None = None

    model_config = ConfigDict(extra="forbid")


class Dac(BaseModel):
    accession: str | None = Field(None, examples=["JGAC000001"])
    alias: str | None = None
    contacts: list[Person] | None = None
    attributes: list[Attribute] | None = None

    model_config = ConfigDict(extra="forbid")


class AccessControl(BaseModel):
    policy: Policy | None = None
    dac: Dac | None = None

    model_config = ConfigDict(extra="forbid")


# === Relations ===


class RelationSource(BaseModel):
    """関係の起点。type はオブジェクトの種類。

    record 内のオブジェクトを accession で指し、accession が無ければ alias で指す。
    SRA の alias は record の中でも一意とは限らないので、accession が無く alias も
    一意でないときは、その種類の list の中の位置 (0 始まり) を index に書く。
    """

    type: str | None = Field(None, examples=["sample"])
    alias: str | None = None
    accession: str | None = None
    index: int | None = Field(None, ge=0)

    model_config = ConfigDict(extra="forbid")


class RelationTarget(BaseModel):
    """関係の相手。

    db が外部 DB の名前なら、id はその DB での番号。
    db がオブジェクトの種類("sample", "experiment", ...)なら、相手はその種類の
    オブジェクトで、id は alias、accession は accession。相手がこの record の中に
    あるかどうかは表さず、読む側が accession か (center_name, alias) で探す。
    SRA の参照は refname と accession を同時に書けるので、片方に寄せると戻せない。
    center_name は alias の名前空間(SRA の refcenter)。
    """

    url: str | None = None
    db: str | None = Field(None, examples=["biosample"])
    id: str | None = Field(None, examples=["SAMD00123456"])
    accession: str | None = None
    center_name: str | None = None
    identifiers: list[Identifier] | None = None

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
