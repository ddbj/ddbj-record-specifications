from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# === Common types ===


class Organism(BaseModel):
    """生物種。最小限の項目だけを持ち、strain や isolate などは attributes に置く。"""

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
    department: str | None = Field(None, examples=["DNA Data Bank of Japan"])
    address: Address | None = None
    ror_id: str | None = Field(None, examples=["https://ror.org/01xq5f0"])

    model_config = ConfigDict(extra="forbid")


class Person(BaseModel):
    """人。role はこの場所での役割で、同じ人が複数の役割を持つときは Person を役割の数だけ書く。"""

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
    """GFF の record 全体の情報。feature ごとの値 (source 列、score 列など) は Feature に置く。"""

    version: str | None = Field(None, examples=["3"])
    pragmas: list[str] | None = None
    source_tool: str | None = Field(None, examples=["DFAST"])

    model_config = ConfigDict(extra="forbid")


class Provenance(BaseModel):
    """record の来歴。変換元の形式と分類、GFF の record 全体の情報。

    変換元ごとに持つ情報が違うので、知らないキーも受け取る (extra="allow")。分かっている情報は型付きのフィールドに置く。
    """

    source_format: str | None = Field(None, examples=["GFF"])
    # WGS / GNM / MAG など。record は「何の record か」を示すフィールドを持たないので、変換元の分類はここに置く。
    submission_category: str | None = Field(None, examples=["WGS"])
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
    """ST.26 (WIPO) の特許配列リストの出願情報。来歴ではなく、登録の内容そのもの。"""

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
    # applicant_name / inventor_name のラテン文字の翻字。
    applicant_name_latin: str | None = None
    inventor_name: str | None = None
    inventor_name_latin: str | None = None
    # 言語ごとの発明の名称。
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
    # 先頭の人が連絡先。
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
    # BP は sample_scope / material / capture が "other" のとき Target/Description に、
    # method が "other" のとき Method 本文に説明を要求する（BP_R0009-R0013, BP_R0019）。
    # 説明を持てないと「説明が無い」と誤検知するので、選択肢と対で保持する。
    description: str | None = None
    method_description: str | None = None
    # data_type ごとの説明。data_types と対にするため relevance と同じ dict[str, str]。
    data_type_descriptions: dict[str, str] | None = None

    model_config = ConfigDict(extra="forbid")


class LocusTagPrefix(BaseModel):
    """locus_tag prefix と、それを申告した BioSample の対。

    BP は prefix 単独では検証できない（BP_R0021 が prefix と BioSample の組を
    BioSample DB と突き合わせ、BP_R0022 が biosample_id の形式を見る）。
    Trad のように対になる BioSample が無い場合は biosample_id を省く。
    """

    prefix: str | None = Field(None, examples=["ECK12"])
    biosample_id: str | None = Field(None, examples=["SAMD00123456"])

    model_config = ConfigDict(extra="forbid")


class ProjectLegacy(BaseModel):
    """SRA XSD 1.5 より前の STUDY にだけある要素。"""

    # DESCRIPTOR/PROJECT_ID(NCBI Genome Project の番号)
    project_id: str | None = None

    model_config = ConfigDict(extra="forbid")


class Project(BaseModel):
    accession: str | None = Field(None, examples=["PRJDB12345"])
    alias: str | None = None
    # BioProject の ProjectDescr/Name。title とは別の短い名前。
    name: str | None = None
    title: str | None = None
    description: str | None = None
    # BioProject の構造の種類 ("primary" / "umbrella")。研究の種類は study_types に置く。
    project_type: str | None = Field(None, examples=["primary"])
    # project_type が "umbrella" のときの種類。
    umbrella_subtype: str | None = Field(None, examples=["eComparativeGenomics"])
    # umbrella_subtype が "other" のときの説明（BP_R0008）。
    umbrella_subtype_description: str | None = None
    # SRA / JGA の研究の種類 ("WGS"、"Case-Control" など)。
    study_types: list[str] | None = None
    organism: Organism | None = None
    publications: list[Publication] | None = None
    grants: list[Grant] | None = None
    keywords: list[str] | None = None
    # BioProject の Relevance。選んだ分野と、その説明 (BP は分野ごとに文字列を書ける)。
    relevance: dict[str, str] | None = None
    locus_tag_prefix: list[LocusTagPrefix] | None = None
    # BioProject の ProjectTypeSubmission の Target と Method。
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
    # SRA の DESCRIPTION、BioSample の Comment/Paragraph。
    description: str | None = None
    organism: Organism | None = None
    attributes: list[Attribute] | None = None
    # BioSample の package。
    package: str | None = Field(None, examples=["MIGS.ba"])
    # JGA の sample の提供者と、群 ("case" / "control" など)。
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
    # "single" / "paired"。
    layout: str | None = Field(None, examples=["paired"])
    # paired の insert size とその標準偏差。
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
    instrument_model: str | None = Field(None, examples=["Illumina HiSeq 2500"])
    # JGA の array の名前・説明・提供元。
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
    read_class: str | None = Field(None, examples=["Application Read"])
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
    # 前の step の step_index。最初の step は "NIL"。
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
    # SRA の DESIGN_DESCRIPTION。
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
    # JGA の、暗号化する前のファイルの checksum。
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
    # JGA の data の種類 ("sequencing"、"array"、"metabolite"、"image")。
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
    # SRA と JGA の analysis の種類を、1 つの語彙で持つ。
    analysis_type: str | None = Field(None, examples=["de_novo_assembly"])
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


# === Investigation (GEA: MAGE-TAB IDF / SDRF) ===


class ExperimentalFactor(BaseModel):
    """IDF の Experimental Factor Name / Type の 1 組。"""

    name: str | None = Field(None, examples=["treatment"])
    type: str | None = Field(None, examples=["compound"])

    model_config = ConfigDict(extra="forbid")


class Protocol(BaseModel):
    """IDF の Protocol Name / Type / Description の 1 組 (CIBEX の Protocol も)。

    name は SDRF の Protocol REF から指される。
    """

    name: str | None = Field(None, examples=["P-GEAD-16"])
    type: str | None = Field(None, examples=["nucleic acid extraction protocol"])
    description: str | None = None

    model_config = ConfigDict(extra="forbid")


class SdrfSource(BaseModel):
    """SDRF の Source のノード。

    comments は SDRF の Comment[x] の列 (name が x)。Submission.comments のような自由記述ではない。
    """

    name: str | None = None
    characteristics: list[Attribute] | None = None
    comments: list[Attribute] | None = None

    model_config = ConfigDict(extra="forbid")


class SdrfExtract(BaseModel):
    name: str | None = None
    # このノードを作るのに使った protocol。SDRF でこのノードの前に並ぶ Protocol REF。
    protocol_refs: list[str] | None = None
    material_type: str | None = Field(None, examples=["total RNA"])
    comments: list[Attribute] | None = None

    model_config = ConfigDict(extra="forbid")


class SdrfLabeledExtract(BaseModel):
    name: str | None = None
    protocol_refs: list[str] | None = None
    label: str | None = Field(None, examples=["Cy3"])
    comments: list[Attribute] | None = None

    model_config = ConfigDict(extra="forbid")


class SdrfAssay(BaseModel):
    name: str | None = None
    protocol_refs: list[str] | None = None
    technology_type: str | None = Field(None, examples=["array assay"])
    array_design_ref: str | None = Field(None, examples=["A-GEAD-210"])
    comments: list[Attribute] | None = None

    model_config = ConfigDict(extra="forbid")


class SdrfDataFile(BaseModel):
    """SDRF のデータファイルの列の 1 つ。

    type は列の名前 ("Array Data File" / "Derived Array Data File" /
    "Array Data Matrix File" / "Derived Array Data Matrix File")。
    File を使わない: SDRF が書くのはファイルの名前だけで、checksum などは登録者が名前を付けた
    Comment[...] の列 (Comment[Array Data File md5] など) として書かれる。
    """

    type: str | None = Field(None, examples=["Array Data File"])
    name: str | None = Field(None, examples=["sample1.CEL"])
    protocol_refs: list[str] | None = None
    comments: list[Attribute] | None = None

    model_config = ConfigDict(extra="forbid")


class SdrfFactorValue(BaseModel):
    """SDRF の Factor Value[name] の列と、その後の Unit[unit_type] の列。"""

    name: str | None = Field(None, examples=["time"])
    value: str | None = Field(None, examples=["24"])
    unit: str | None = Field(None, examples=["hour"])
    unit_type: str | None = Field(None, examples=["time unit"])

    model_config = ConfigDict(extra="forbid")


class SdrfRow(BaseModel):
    """SDRF の 1 行。Source から始まり、protocol を経てデータファイルに至る 1 本の道筋。

    同じ名前のノードが行ごとに違う値を持つことがある (保存された SDRF にある) ので、
    ノードを行の間で共有せず、行ごとに持つ。
    """

    source: SdrfSource | None = None
    extract: SdrfExtract | None = None
    labeled_extract: SdrfLabeledExtract | None = None
    assay: SdrfAssay | None = None
    data_files: list[SdrfDataFile] | None = None
    factor_values: list[SdrfFactorValue] | None = None

    model_config = ConfigDict(extra="forbid")


class CibexExperiment(BaseModel):
    title: str | None = None
    design_type: str | None = None
    factor: str | None = None
    common_reference: str | None = None
    quality_control_description: str | None = None
    number_of_hybridizations: int | None = None
    description: str | None = None

    model_config = ConfigDict(extra="forbid")


class CibexSubmitter(BaseModel):
    """Person に写さない: 住所、所属、研究室が 1 つずつの自由記述で、Organization の形に分けられない。"""

    first_name: str | None = None
    middle_initials: str | None = None
    last_name: str | None = None
    organization: str | None = None
    department: str | None = None
    laboratory: str | None = None
    address: str | None = None

    model_config = ConfigDict(extra="forbid")


class CibexReference(BaseModel):
    """Publication に写さない: 著者は 1 つの文字列、頁は「13784-9」のような 1 つの値、年は日付でない。"""

    title: str | None = None
    author: str | None = None
    journal: str | None = None
    year: str | None = None
    volume: str | None = None
    issue: str | None = None
    page: str | None = None
    pubmed_id: str | None = None

    model_config = ConfigDict(extra="forbid")


class CibexDataField(BaseModel):
    """データファイルの列の 1 つと、その説明 (CIBEX の * data text field)。"""

    field: str | None = Field(None, examples=["F532 Median"])
    description: str | None = None

    model_config = ConfigDict(extra="forbid")


class CibexArrayDesign(BaseModel):
    accession: str | None = Field(None, examples=["CAR273"])
    model_name: str | None = None
    technology_type: str | None = None
    surface_type: str | None = None
    number_of_features: int | None = None
    reporter_type: str | None = None
    strand_type: str | None = None
    substrate_type: str | None = None
    attachment: str | None = None
    design_provider: str | None = None
    array_design_protocol: str | None = None
    description: str | None = None
    file: str | None = None
    data_fields: list[CibexDataField] | None = None

    model_config = ConfigDict(extra="forbid")


class CibexSample(BaseModel):
    name: str | None = None
    organism: str | None = None
    organism_part: str | None = None
    sex: str | None = None
    age: str | None = None
    strain_or_line: str | None = None
    cell_line: str | None = None
    cell_type: str | None = None
    developmental_stage: str | None = None
    disease_state: str | None = None
    genetic_modification: str | None = None
    individual: str | None = None
    individual_genetic_characteristics: str | None = None
    growth_condition_protocol: str | None = None
    treatment_protocol: str | None = None
    biosource_provider: str | None = None
    description: str | None = None

    model_config = ConfigDict(extra="forbid")


class CibexLabeledExtract(BaseModel):
    label: str | None = None
    label_compound: str | None = None
    extraction_protocol: str | None = None
    labeling_protocol: str | None = None
    pooling_protocol: str | None = None

    model_config = ConfigDict(extra="forbid")


class CibexHybridization(BaseModel):
    name: str | None = None
    array_design_accession: str | None = None
    hybridization_protocol: str | None = None
    scanning_protocol: str | None = None
    description: str | None = None
    file: str | None = None
    data_fields: list[CibexDataField] | None = None

    model_config = ConfigDict(extra="forbid")


class CibexSummary(BaseModel):
    name: str | None = None
    normalization_protocol: str | None = None
    transformation_protocol: str | None = None
    description: str | None = None
    file: str | None = None
    data_fields: list[CibexDataField] | None = None

    model_config = ConfigDict(extra="forbid")


class Cibex(BaseModel):
    """GEA に移す前の CIBEX の登録 (CBX)。GEA の experiment 1 つに 1 つ対応する。"""

    accession: str | None = Field(None, examples=["CBX100"])
    release_date: str | None = None
    experiment: CibexExperiment | None = None
    submitters: list[CibexSubmitter] | None = None
    references: list[CibexReference] | None = None
    protocols: list[Protocol] | None = None
    array_designs: list[CibexArrayDesign] | None = None
    samples: list[CibexSample] | None = None
    labeled_extracts: list[CibexLabeledExtract] | None = None
    hybridizations: list[CibexHybridization] | None = None
    summaries: list[CibexSummary] | None = None

    model_config = ConfigDict(extra="forbid")


class InvestigationLegacy(BaseModel):
    """CIBEX から移した experiment にだけある、IDF の Comment[CIBEX *] と、CIBEX の元の登録。"""

    cibex_accept_date: str | None = None
    cibex_public_release_date: str | None = None
    cibex_submitter: str | None = None
    cibex: Cibex | None = None

    model_config = ConfigDict(extra="forbid")


class Investigation(BaseModel):
    """GEA の experiment (E-GEAD)。MAGE-TAB の IDF と SDRF。"""

    accession: str | None = Field(None, examples=["E-GEAD-1005"])
    alias: str | None = None
    identifiers: list[Identifier] | None = None
    title: str | None = None
    description: str | None = None
    magetab_version: str | None = Field(None, examples=["1.1"])
    experimental_designs: list[str] | None = None
    experimental_factors: list[ExperimentalFactor] | None = None
    persons: list[Person] | None = None
    protocols: list[Protocol] | None = None
    publications: list[Publication] | None = None
    public_release_date: str | None = None
    sdrf_file: str | None = None
    sdrf: list[SdrfRow] | None = None
    # 以下は GEA が IDF の Comment[...] に書くもの。
    experiment_type: str | None = Field(None, examples=["transcription profiling by array"])
    channel_type: str | None = Field(None, examples=["single-channel"])
    # SDRF の Array Design REF をまとめたもの。
    array_design_ref: str | None = None
    last_update_date: str | None = None
    # ヒトのデータの公開を、NBDC / DBCLS のデータアクセス委員会が承認したことを述べる文。
    nbdc_approval: str | None = None
    dbcls_approval: str | None = None
    legacy: InvestigationLegacy | None = None

    model_config = ConfigDict(extra="forbid")


# === Array Design (GEA: A-GEAD) ===


class TermSource(BaseModel):
    name: str | None = None
    file: str | None = None
    version: str | None = None

    model_config = ConfigDict(extra="forbid")


class ArrayDesignLegacy(BaseModel):
    cibex_public_release_date: str | None = None

    model_config = ConfigDict(extra="forbid")


class ArrayDesign(BaseModel):
    """GEA のアレイ設計 (A-GEAD)。ADF の見出しと、表を含むファイルそのもの。

    ADF の表 (プローブ 1 つ 1 行) は装置メーカーごとの形式で、ファイルとして保管する。見出しの
    欄は file の見出しから読んだもので、正本は file。
    """

    accession: str | None = Field(None, examples=["A-GEAD-210"])
    alias: str | None = None
    name: str | None = None
    version: str | None = None
    provider: str | None = None
    printing_protocol: str | None = None
    technology_type: str | None = None
    surface_type: str | None = None
    substrate_type: str | None = None
    sequence_polymer_type: str | None = None
    term_sources: list[TermSource] | None = None
    organism: Organism | None = None
    description: str | None = None
    public_release_date: str | None = None
    submitted_name: str | None = None
    file: File | None = None
    legacy: ArrayDesignLegacy | None = None

    model_config = ConfigDict(extra="forbid")


# === Sequences & Entries ===


class Qualifier(BaseModel):
    """INSDC の qualifier の値。alias は record の中での識別子。"""

    alias: str | None = None
    value: str | None = None

    model_config = ConfigDict(extra="forbid")


class Source(BaseModel):
    organism: Organism | None = None
    mol_type: str | None = Field(None, examples=["genomic DNA"])
    qualifiers: dict[str, list[Qualifier]] | None = None

    model_config = ConfigDict(extra="forbid")


class SourceFeature(BaseModel):
    """INSDC の source feature。

    definition は DEFINITION 行 (ff_definition) をそのまま持つ。`@@[organism]@@` のような template は展開しない。展開は record を読む側が行う。
    """

    alias: str | None = None
    location: str | None = Field(None, examples=["1..2277985"])
    source: Source | None = None
    definition: list[str] | None = None

    model_config = ConfigDict(extra="forbid")


class Entry(BaseModel):
    # version を含む ("AB123456.1")。alias は登録者が付けた名前。
    accession: str | None = Field(None, examples=["AB123456.1"])
    alias: str | None = Field(None, examples=["contig_001"])
    name: str | None = None
    type: str | None = Field(None, examples=["chromosome"])
    topology: str | None = Field(None, examples=["circular"])
    # GenBank の division。
    division: str | None = Field(None, examples=["BCT"])
    sequence: str | None = None
    comments: list[str] | None = None
    source_features: list[SourceFeature] | None = None

    model_config = ConfigDict(extra="forbid")


class StructuredComment(BaseModel):
    """Trad の ST_COMMENT の 1 つ。tagset_id がブロックの種類で、fields はその中の項目と値。"""

    tagset_id: str | None = Field(None, examples=["Genome-Assembly-Data"])
    fields: dict[str, str] | None = None

    model_config = ConfigDict(extra="forbid")


class Sequences(BaseModel):
    seq_prefix: str | None = Field(None, examples=["contig"])
    # 全ての entry の source feature に共通する値。Sample.organism とは別に持つ。
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
    # この feature が載る Entry の alias。
    sequence_id: str | None = None
    qualifiers: dict[str, list[Qualifier]] | None = None
    locus_tag_id: str | None = None
    # GFF の source 列・score 列・phase 列 (0 / 1 / 2)。phase は INSDC の /codon_start と対応する (phase 0 が codon_start 1)。
    source_tool: str | None = None
    score: float | None = None
    phase: int | None = None
    # GFF の Parent 属性。親の Feature の alias。
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
    """JGA の dataset。含む run / analysis と従う policy は relations で指す。"""

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
    """JGA の policy と DAC。"""

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
    """オブジェクトの間の関係と、外部への参照。

    type は "reference" (URL)、"xref" (外部 DB)、"part_of"、"child_of"、"derived_from"、"related_to"、"governed_by"、"managed_by"、"contains"。
    source を省くと、record 全体が起点になる。
    """

    type: str | None = Field(None, examples=["child_of"])
    source: RelationSource | None = None
    target: RelationTarget | None = None
    label: str | None = None
    properties: dict[str, str] | None = None

    model_config = ConfigDict(extra="forbid")


# === DdbjRecord ===


class DdbjRecord(BaseModel):
    schema_version: str | None = Field(None, examples=["v3"])
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
    investigation: Investigation | None = None
    array_design: ArrayDesign | None = None

    model_config = ConfigDict(extra="forbid")
