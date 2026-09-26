# v3 スキーマ仕様

DDBJ Record v3 のデータモデル定義。
全形式（Trad, BP, BS, SRA, JGA, ST.26, GFF, Assembly, GEA）を統一的に扱う JSON フォーマットを定義する。

## 設計方針

- フラットなスキーマ + バリデーションルール方式を採用（詳細は [v3-validator.md](./v3-validator.md)）
  - 全フィールド nullable。record_type のような判別フィールドは持たない
  - 「何として有効か」は validation rules の通過結果から導出する
- v2 以前との後方互換性は不要
- この repository が converter + validator を兼ねる
- validation は datasource / status / submission_stage に応じて挙動を変える（plugin 化）
- [record-idm](https://github.com/ddbj/record-idm) の概念（2D status model, relation graph）を取り込む
- 概念の共通化: DB ごとのサイロではなく、ontology に基づいてフィールドを統合する
  - SRA study + BioProject → 統一 "project"
  - SRA sample + BioSample → 統一 "sample"
  - 共通化による複雑性は validator / converter で吸収する（例: BP → record → BP round-trip）
- record は純粋な data。status や validation config は外付け

## 対応形式のスコープ

v3 で扱う形式の一覧と、それぞれが関わる DDBJ データベース。

| 形式 | 関連 DB | 備考 |
|------|---------|------|
| Trad (GNM) | DDBJ | complete ゲノム |
| Trad (WGS) | DDBJ | draft ゲノム |
| Trad (MAG) | DDBJ | Metagenome-Assembled Genome |
| Trad (SAG) | DDBJ | Single-cell Amplified Genome |
| Trad (haplotype) | DDBJ | ハプロタイプ構成ゲノム |
| BioProject (primary) | BioProject | 研究プロジェクト |
| BioProject (umbrella) | BioProject | 複数 BP をまとめる上位プロジェクト |
| BioSample | BioSample | 試料情報 |
| SRA/DRA | SRA | シーケンスデータ（submission/study/experiment/run/analysis/sample） |
| JGA/AGD | JGA | 制限公開データ（study/experiment/analysis/dataset/policy/DAC） |
| ST.26 | DDBJ (PAT division) | 特許配列リスト（WIPO Standard ST.26、詳細は [v3-converter.md](./v3-converter.md#st26-wipo-standard-st26)） |
| GFF | DDBJ | ゲノムアノテーション |
| Assembly | DDBJ + NCBI | NCBI Assembly 登録、accession、index 生成 |
| GEA | GEA | 発現データ（experiment の MAGE-TAB、アレイ設計、前身 CIBEX の登録。詳細は [v3-gea.md](./v3-gea.md)） |

MetaboBank, JVar は現在スコープ外。将来の拡張候補。

## Top-level 構造

```
DdbjRecord (all fields Optional/None)
├── schema_version: str
├── provenance: Provenance | None       # data の来歴記録（変換元形式、GFF メタデータ等）
├── submission: Submission | None       # submitters, hold_date, comments, st26, sra
├── project: Project | None             # = BP + SRA Study + JGA Study
│   ├── name, project_type              # BP Name (短縮名), "primary"/"umbrella"
│   ├── umbrella_subtype                # umbrella 固有の subtype
│   ├── study_types                     # "WGS", "Case-Control", ...
│   ├── publications, grants, keywords, relevance
│   ├── locus_tag_prefix
│   └── target                          # sample_scope, material, capture, method, data_types
├── samples: list[Sample] | None        # = BS + SRA Sample + JGA Sample (EAV)
├── experiments: list[Experiment] | None # SRA/JGA experiment (library, platform)
├── runs: list[Run] | None              # SRA Run + JGA Data (data_blocks → files)
├── analyses: list[Analysis] | None     # SRA/JGA analysis (analysis_type, data_blocks → files)
├── sequences: Sequences | None         # Trad/ST.26 (entries, common_source)
├── features: list[Feature] | None      # INSDC feature table
├── assembly: Assembly | None           # assembly accession, name, level
├── datasets: list[Dataset] | None      # JGA Dataset（独立）
├── relations: list[Relation] | None    # 外部参照 (URL, db_xref) + 意味的関係 (child_of, ...)
├── access_control: AccessControl | None # JGA Policy/DAC
├── investigation: Investigation | None # GEA experiment（MAGE-TAB の IDF / SDRF）
└── array_design: ArrayDesign | None    # GEA アレイ設計（ADF）
```

設計上の決定:

- **全フィールド nullable**: 全フィールド `T | None`。record_type のような判別フィールドは不要。validation rules の通過結果から「何として有効か」を導出する
- **段階的更新**: 1 つの record ファイルを段階的に更新していく運用モデル（project 登録 → accession 追記 → sample 追記 → ...）
- **submission set**: 1 つの DdbjRecord に複数 DB の情報を含めることで、submission set を自然に表現
- **status**: record に含めない。record-idm の外部メタデータ
- **ObjectType 基底モデル**: 作らない。accession, alias 等は各モデルが個別に持つ
- **GFF トップレベル廃止**: GFF は入力フォーマットであり record の構成要素ではない。features に正規化し、GFF 固有情報は provenance に退避
- **Links と Relations の統合**: 外部参照（URL, db_xref）も意味的関係も広義の relation として `relations` に統合。旧 `links` フィールドは廃止
- **submission_category**: 判別フィールドに該当するため、モデルに持たない。変換元の分類情報は provenance に格納

## 共通型

### Organism

Project, Sample, Sequences (common_source) で横断的に使われる。最小限のフィールドに絞る（strain, isolate 等は Sample attributes (EAV) で扱う）。

```python
class Organism(BaseModel):
    name: str | None              # "Homo sapiens"
    common_name: str | None       # "human" (SRA COMMON_NAME)
    taxonomy_id: int | None       # NCBI Taxonomy ID (e.g., 9606)
```

### Date

型は `str | None`。ISO 8601 形式で精度のバリエーションを許容（`"2024-01-15T09:00:00Z"`, `"2024-01-15"`, `"2024-01"`, `"2024"`）。形式の検証は validation rule で行う。submitter 指定の date のみ record に含め、archive 管理の日付（created, modified, published 等）は外部メタデータ。

### Person / Organization / Address

```python
class Address(BaseModel):
    country: str | None
    state: str | None
    city: str | None
    street: str | None
    postal_code: str | None

class Organization(BaseModel):
    name: str | None
    abbreviation: str | None
    url: str | None
    role: str | None              # "owner", "participant", ...
    type: str | None              # "institution", "company", "government", ...
    department: str | None
    address: Address | None
    ror_id: str | None

class Person(BaseModel):
    name: str | None              # full name ("Hanako Mishima")
    first_name: str | None        # "Hanako"
    last_name: str | None         # "Mishima"
    abbreviation: str | None      # "Mishima,H." (Trad)
    email: str | None
    phone: str | None
    orcid: str | None
    role: str | None              # "PI", "submitter", "head", "contact", ...
    organizations: list[Organization] | None
```

role は Entity に持たせる（flat pragmatic）。同一人物が複数の role を持つ場合は Person オブジェクトを複製する。

### Identifier

accession 以外の識別子。SRA の IDENTIFIERS（PRIMARY_ID / SECONDARY_ID / EXTERNAL_ID / SUBMITTER_ID / UUID）を 1 つの list で持つ。

```python
class Identifier(BaseModel):
    type: str | None              # "primary", "secondary", "external", "submitter", "uuid"
    value: str | None
    label: str | None
    namespace: str | None         # external / submitter の名前空間（"BioSample", "NGDC", ...）
```

### ExternalRef

record の中の値そのものが外部の何かを指すときに使う（参照アセンブリの名前、targeted locus のプローブなど）。record のオブジェクトの間の関係は [Relations](#relations) に置く。

```python
class ExternalRef(BaseModel):
    url: str | None
    db: str | None
    id: str | None
    label: str | None
```

### accession / alias

各モデルに持たせる識別子フィールド。

```python
# Project, Sample, Experiment, Run, Analysis, Entry, Dataset, Assembly,
# Policy, Dac, Investigation, ArrayDesign に共通:
accession: str | None         # 登録後に付与 ("PRJDB12345", "SAMD00123456", ...)
alias: str | None             # 登録前のローカル名 (SRA refname 等)

# Feature, Qualifier:
alias: str | None             # ローカル識別子（accession は持たない）
```

- 登録前は alias のみ、登録後に accession が追記される
- alias は submission (record) 内で unique。ただし SRA から写した record では重なることがあり、relation は accession か位置で指す（[v3-sra.md](./v3-sra.md)）
- submit 時に submission_id が namespace になる（例: `<submission_id>::bioproject::my-project-01`）
- SRA 由来のオブジェクトは center_name / broker_name と、accession 以外の識別子（`identifiers`）も持つ。SRA XML は各オブジェクトにそれぞれ書けるので、submission の値から導出すると戻せない（[v3-sra.md](./v3-sra.md)）
- Feature / Qualifier は accession を持たない。alias のみで識別する（Feature は type + location でも識別可能）

## Submission

提出行為のメタデータ。ST.26 特許メタデータも提出文脈の一次データとしてここに配置する。

```python
class InventionTitle(BaseModel):
    title: str | None                  # 発明名称
    language_code: str | None          # ISO 639-1 (e.g., "ja", "en")

class ApplicationIdentification(BaseModel):
    ip_office_code: str | None         # WIPO ST.3 (e.g., "JP", "US")
    application_number_text: str | None
    filing_date: str | None            # ISO 8601

class St26Meta(BaseModel):
    dtd_version: str | None            # "V1_3"
    software_name: str | None
    software_version: str | None
    production_date: str | None        # ISO 8601
    original_language: str | None      # ISO 639-1
    non_english_language: str | None   # ISO 639-1
    applicant_file_reference: str | None
    application: ApplicationIdentification | None
    earliest_priority: ApplicationIdentification | None
    applicant_name: str | None
    applicant_name_latin: str | None   # ラテン文字翻字
    inventor_name: str | None
    inventor_name_latin: str | None    # ラテン文字翻字
    invention_titles: list[InventionTitle] | None

class SraContact(BaseModel):          # SRA CONTACTS/CONTACT
    name: str | None
    inform_on_status: str | None       # 経過を知らせる宛先
    inform_on_error: str | None        # エラーを知らせる宛先

class SraActionLegacy(BaseModel):     # SRA XSD 1.5 より前
    hold_for_period: str | None
    notes: str | None

class SraAction(BaseModel):           # SRA ACTIONS/ACTION（書かれた順）
    type: str | None                   # "ADD", "MODIFY", "VALIDATE", "HOLD", "RELEASE", "SUPPRESS", "PROTECT"
    source: str | None                 # ADD / MODIFY / VALIDATE の対象ファイル
    object_type: str | None            # 同じく、その文書の種類（@schema）
    target: str | None                 # HOLD / RELEASE / SUPPRESS の対象 accession
    hold_until_date: str | None
    legacy: SraActionLegacy | None

class SraSubmissionLegacy(BaseModel): # SRA XSD 1.5 より前
    submission_id: str | None
    files: list[File] | None           # FILES/FILE

class SraSubmission(BaseModel):       # SRA の登録手続きについての情報
    lab_name: str | None
    submission_date: str | None
    submission_comment: str | None
    contacts: list[SraContact] | None
    actions: list[SraAction] | None
    legacy: SraSubmissionLegacy | None

class Submission(BaseModel):
    accession: str | None              # DRA
    alias: str | None
    title: str | None
    submitters: list[Person] | None   # submitters[0] = contact person
    hold_date: str | None             # ISO 8601
    comments: list[str] | None        # free-form notes
    st26: St26Meta | None             # ST.26 特許メタデータ
    sra: SraSubmission | None         # SRA の登録手続き
    attributes: list[Attribute] | None
    identifiers: list[Identifier] | None
    center_name: str | None           # SRA
    broker_name: str | None           # SRA
```

v2 submission にあった references, keywords, locus_tag_prefix, division, db_xrefs 等は適切な帰属先に移動済み。

設計上の決定:

- **SRA 配置先**: SRA の SUBMISSION が持つ登録手続きの情報（連絡先、ACTIONS、lab_name など）は、ST.26 と同じく `Submission.sra` にまとめる。accession / alias / title / center_name などは他の DB のオブジェクトと同じ形なので Submission に直接置く
- **ST.26 配置先**: ST.26 特許メタデータ（出願人、発明者、発明名称等）は来歴（provenance）ではなく提出内容の一次データ。Submission.st26 に typed model として配置する
- **多言語対応**: InventionTitle は languageCode 付きで複数言語に対応。applicant_name / inventor_name はラテン文字翻字版も保持
- **attributes**: Submission 固有のカスタムメタデータ用。typed field 優先、残りを EAV

## Project

BioProject + SRA Study + JGA Study の統合。

```python
class Publication(BaseModel):
    title: str | None
    pubmed_id: str | None              # PubMed ID
    doi: str | None
    status: str | None                 # "published", "in_press", "unpublished"
    date: str | None                   # ISO 8601
    journal: str | None
    volume: str | None
    issue: str | None
    pages_from: str | None
    pages_to: str | None
    authors: list[Person] | None
    consortiums: list[str] | None      # BP AuthorSet/Consortium

class Grant(BaseModel):
    title: str | None
    agency: str | None
    id: str | None

class ProjectTarget(BaseModel):
    sample_scope: str | None           # "monoisolate", "multispecies", "environment", ...
    material: str | None               # "genome", "transcriptome", "proteome", ...
    capture: str | None                # "whole", "exome", "targeted_locus", ...
    method: str | None                 # "sequencing", "array", "mass_spec", ...
    data_types: list[str] | None       # "raw_sequence_reads", "assembly", "annotation", ...
    description: str | None            # sample_scope/material/capture が "other" のときの説明
    method_description: str | None     # method が "other" のときの説明
    data_type_descriptions: dict[str, str] | None   # {"other": "..."}

class LocusTagPrefix(BaseModel):
    prefix: str | None                 # "ECK12"
    biosample_id: str | None           # "SAMD00123456"（対になる BioSample が無ければ省略）

class Project(BaseModel):
    accession: str | None              # PRJDB/PRJNA/PRJEB
    alias: str | None
    name: str | None                   # BP ProjectDescr/Name (短縮名、Title とは別)
    title: str | None
    description: str | None
    project_type: str | None           # "primary", "umbrella"
    umbrella_subtype: str | None       # umbrella 固有: "eDisease", "eComparativeGenomics", ...
    umbrella_subtype_description: str | None   # umbrella_subtype が "other" のときの説明
    study_types: list[str] | None      # "WGS", "Case-Control", ...
    organism: Organism | None
    publications: list[Publication] | None
    grants: list[Grant] | None
    keywords: list[str] | None
    relevance: dict[str, str] | None   # {"agricultural": "crop improvement", ...}
    locus_tag_prefix: list[LocusTagPrefix] | None
    target: ProjectTarget | None
    attributes: list[Attribute] | None # STUDY_ATTRIBUTES (TAG/VALUE)
    identifiers: list[Identifier] | None
    center_name: str | None            # SRA
    broker_name: str | None            # SRA
    study_description: str | None      # SRA STUDY_DESCRIPTION（description は STUDY_ABSTRACT）
    center_project_name: str | None    # SRA
    descriptor_center_name: str | None # SRA XSD 1.5d2 の DESCRIPTOR/CENTER_NAME
    new_study_type: str | None         # SRA STUDY_TYPE@new_study_type
    legacy: ProjectLegacy | None       # SRA XSD 1.5 より前

class ProjectLegacy(BaseModel):
    project_id: str | None             # DESCRIPTOR/PROJECT_ID（NCBI Genome Project の番号）
```

設計上の決定:

- **project_type と study_types を分離**: BP の構造種別（primary/umbrella）と SRA/JGA の研究手法/デザインは別概念
- **description と study_description**: `description` は BP の Description と SRA の STUDY_ABSTRACT（研究の要旨）、`study_description` は SRA の STUDY_DESCRIPTION（研究の説明）。SRA は両方を別に書ける
- **Umbrella**: 1 JSON = 1 Project。umbrella は `project_type: "umbrella"` ��表現し、親子関係は `relations` で
- **複数の study を持つ SRA submission**: `project` は 1 つのまま。study が 2 つ以上なら、study ごとに `project` だけの record に分け、experiment からは accession で指す（[v3-sra.md](./v3-sra.md#複数の-study-を持つ-submission)）
- **target**: BP ProjectTypeSubmission 固有の概念を `ProjectTarget` としてネスト
- **division**: project には含めない（Entry レベル or validator 導出）
- **datatype**: project には含めない（assembly.submission_category に統合）
- **relevance**: BP XSD の Relevance は string 値を持てるため `dict[str, str]` で保持
- **"other" の説明を選択肢と対で持つ**: BP は sample_scope / material / capture / method /
  data_type / umbrella_subtype が "other" のとき説明文を要求する（BP_R0008-R0013, BP_R0019）。
  説明を持てない形式だと、説明を書いた登録者に「説明が無い」と言うことになるため、
  選択肢の隣に説明の置き場を用意する。`relevance` が同じ理由で `dict[str, str]` なのと同じ扱い
- **locus_tag_prefix は prefix 単独では検証できない**: BP_R0021 は prefix と BioSample の組を
  BioSample DB と突き合わせ、BP_R0022 は biosample_id の形式を見る。prefix の文字列だけでは
  どちらも判定できないので、対で保持する `LocusTagPrefix` にした。Trad のように対になる
  BioSample が無い形式では `biosample_id` を省く

## Sample

BioSample + SRA Sample + JGA Sample の統合。

```python
class Attribute(BaseModel):
    name: str                          # 必須。空白だけも不可
    value: str | None
    unit: str | None

class Sample(BaseModel):
    accession: str | None              # SAMD/SAMN/SAME
    alias: str | None
    title: str | None
    description: str | None            # SRA DESCRIPTION, BS Comment/Paragraph
    organism: Organism | None
    attributes: list[Attribute] | None # EAV (name/value/unit)
    package: str | None                # "MIGS.ba", "Pathogen.cl.1.0", ...
    donor_id: str | None               # JGA
    sample_group_type: str | None      # JGA: "case", "control", "cancer"
    identifiers: list[Identifier] | None
    center_name: str | None            # SRA
    broker_name: str | None            # SRA
    anonymized_name: str | None        # SRA SAMPLE_NAME/ANONYMIZED_NAME
    individual_name: str | None        # SRA SAMPLE_NAME/INDIVIDUAL_NAME
```

設計上の決定:

- **EAV 維持**: BioSample の ~960 attributes を全て typed fields にするのは非現実的。validation rule で必須/任意を制御
- **common_source との関係**: 統合しない。Sample.organism と Sequences.common_source は役割が異なる（試料メタデータ vs INSDC source feature のデフォルト値）。整合性は validation rule で検証
- **collection_date**: attributes のまま（昇格させるとキリがない）
- **anonymized_name / individual_name**: typed field。attributes に置くと、同じ名前の SAMPLE_ATTRIBUTE と見分けられず SRA XML に戻せない
- **Attribute.name は必須**（空白だけも不可）。名前の無い属性は何の値かが分からず、検証も表示もしようがない。
  `Attribute` は Sample に限らず全エンティティ共通なので、この制約も全 DB に効く。正規化は前後の空白を落とすので、
  `"  "` を許すと正規化の後で名前の無い属性になる

## Experiment

SRA Experiment + JGA Experiment の統合。

```python
class LibraryDescriptor(BaseModel):
    name: str | None                   # library name
    strategy: str | None               # "WGS", "RNA-Seq", "ChIP-Seq", ...
    source: str | None                 # "GENOMIC", "TRANSCRIPTOMIC", ...
    selection: str | None              # "RANDOM", "PCR", "cDNA", ...
    layout: str | None                 # "single", "paired"
    nominal_length: int | None         # paired-end の insert size
    nominal_sdev: float | None         # paired-end の標準偏差
    construction_protocol: str | None  # free text
    pooling_strategy: str | None       # SRA XSD 1.5d2
    legacy: LibraryLegacy | None

class LibraryLegacy(BaseModel):        # SRA XSD 1.5 より前
    orientation: str | None            # PAIRED@ORIENTATION

class TargetedLocus(BaseModel):
    name: str | None                   # "16S rRNA", "exome", ...
    description: str | None
    probe_set: ExternalRef | None

class ColorMatrixEntry(BaseModel):     # SOLiD の 2 塩基と色の対応
    dibase: str | None
    color: str | None

class Platform(BaseModel):
    type: str | None                   # "ILLUMINA", "PACBIO_SMRT", ...
    instrument_model: str | None       # "Illumina HiSeq 2500", ...
    array_name: str | None             # JGA array の場合
    array_description: str | None      # JGA array の場合
    array_provider: str | None         # JGA array の場合
    legacy: PlatformLegacy | None

class PlatformLegacy(BaseModel):       # SRA XSD 1.5 より前の、装置ごとの運転条件
    cycle_count: int | None            # ILLUMINA, ABI_SOLID
    sequence_length: int | None        # ILLUMINA, ABI_SOLID
    cycle_sequence: str | None         # ILLUMINA
    flow_count: int | None             # LS454, HELICOS
    flow_sequence: str | None          # LS454, HELICOS
    key_sequence: str | None           # LS454
    color_matrix: list[ColorMatrixEntry] | None  # ABI_SOLID
    color_matrix_code: str | None      # ABI_SOLID

class RelativeOrder(BaseModel):
    follows_read_index: int | None
    precedes_read_index: int | None

class Basecall(BaseModel):             # EXPECTED_BASECALL_TABLE の 1 行
    value: str | None                  # その位置に来るはずの配列（バーコードなど）
    read_group_tag: str | None
    min_match: int | None
    max_mismatch: int | None
    match_edge: str | None             # "start", "end", "full"

class BasecallTable(BaseModel):
    base_coord: int | None
    default_length: int | None
    basecalls: list[Basecall] | None

class ExpectedBasecall(BaseModel):     # READ_SPEC/EXPECTED_BASECALL
    value: str | None
    base_coord: int | None
    default_length: int | None

class ReadSpec(BaseModel):
    read_index: int | None
    read_label: str | None
    read_class: str | None             # "Application Read", "Technical Read", ...
    read_type: str | None              # "Forward", "Reverse", ...
    # 読みの位置は次の 3 つ（1.5 より前は legacy の 2 つを加えた 5 つ）のどれか 1 つで決める
    base_coord: int | None
    relative_order: RelativeOrder | None
    expected_basecall_table: BasecallTable | None
    legacy: ReadSpecLegacy | None

class ReadSpecLegacy(BaseModel):       # SRA XSD 1.5 より前
    cycle_coord: int | None
    expected_basecall: ExpectedBasecall | None

class SpotDescriptor(BaseModel):
    spot_length: int | None
    reads: list[ReadSpec] | None
    legacy: SpotDescriptorLegacy | None

class SpotDescriptorLegacy(BaseModel): # SRA XSD 1.5 より前
    number_of_reads_per_spot: int | None
    adapter_spec: str | None

class PipelineStep(BaseModel):
    step_index: str | None
    prev_step_indexes: list[str] | None  # "NIL" for first step
    program: str | None
    version: str | None
    section_name: str | None
    notes: str | None

class Gap(BaseModel):                  # DESIGN/GAP_DESCRIPTOR/GAP
    type: str | None                   # "MatePair", "PairedEnd", "Tandem"
    orientation: str | None
    link5: str | None
    link3: str | None
    min_length: int | None
    max_length: int | None
    mean: float | None
    stdev: float | None

class BaseCalling(BaseModel):          # PROCESSING/BASE_CALLS
    base_caller: str | None
    sequence_space: str | None         # "Base Space", "Color Space"

class QualityScoring(BaseModel):       # PROCESSING/QUALITY_SCORES
    qtype: str | None                  # "phred", "other"
    quality_scorer: str | None
    number_of_levels: int | None
    multiplier: float | None

class ExperimentLegacy(BaseModel):     # SRA XSD 1.5 より前
    expected_number_runs: int | None
    gaps: list[Gap] | None
    base_calling: BaseCalling | None
    quality_scoring: list[QualityScoring] | None

class ReadLabel(BaseModel):
    value: str | None
    read_group_tag: str | None

class PoolMember(BaseModel):           # SAMPLE_DESCRIPTOR/POOL/MEMBER
    sample: RelationTarget | None
    member_name: str | None            # runs[].data_blocks[].member_name から指される
    proportion: float | None
    read_labels: list[ReadLabel] | None

class Pool(BaseModel):
    default_member: PoolMember | None
    members: list[PoolMember] | None

class Experiment(BaseModel):
    accession: str | None              # DRX/SRX/ERX
    alias: str | None
    title: str | None
    description: str | None            # SRA DESIGN_DESCRIPTION
    library: LibraryDescriptor | None
    platform: Platform | None
    targeted_loci: list[TargetedLocus] | None
    spot_descriptor: SpotDescriptor | None  # SRA SPOT_DESCRIPTOR
    processing: list[PipelineStep] | None   # SRA PROCESSING/PIPELINE
    attributes: list[Attribute] | None # EXPERIMENT_ATTRIBUTES (TAG/VALUE)
    identifiers: list[Identifier] | None
    center_name: str | None
    broker_name: str | None
    pool: Pool | None                  # 1 experiment に複数の sample を混ぜたとき
    sample_demux_directive: str | None # "leave_as_pool", "submitter_demultiplexed"
    legacy: ExperimentLegacy | None
```

設計上の決定:

- **controlled vocabulary**: 全て `str | None`。許容値は YAML 外部定義 + validation rule で制御（XSD enum は頻繁に更新されるため）
- **JGA array platform**: Platform に flat に統合
- **POOL**: 混ぜた sample は `relations` でなく `pool.members[].sample` に置く。member は sample への参照に加えて read label の list を持ち、relation の `properties`（`dict[str, str]`）には収まらない。run の data block は member_name でこれを指す
- **legacy**: SRA XSD 1.5 より前の登録にだけある要素は、各モデルの `legacy` にまとめる（[v3-sra.md](./v3-sra.md)）

## Run

SRA Run + JGA Data の統合。

```python
class File(BaseModel):
    filename: str | None
    filetype: str | None               # "fastq", "bam", "cram", "CEL", ...
    checksum_method: str | None        # "MD5"
    checksum: str | None
    unencrypted_checksum: str | None   # JGA: checksum before encryption
    quality_scoring_system: str | None # "phred", "log-odds"
    quality_encoding: str | None       # "ascii", "decimal", "hexadecimal"
    ascii_offset: str | None           # "!", "@"
    read_labels: list[str] | None
    legacy: FileLegacy | None

class FileLegacy(BaseModel):           # SRA XSD 1.5 より前
    data_series_labels: list[str] | None

class DataBlock(BaseModel):            # SRA / JGA の DATA_BLOCK
    name: str | None
    serial: int | None
    member_name: str | None            # experiments[].pool.members[].member_name を指す
    files: list[File] | None
    legacy: DataBlockLegacy | None

class DataBlockLegacy(BaseModel):      # SRA XSD 1.5 より前の、装置上の位置と読みの数
    sector: int | None
    region: int | None
    format_code: int | None
    number_channels: int | None
    total_spots: int | None
    total_reads: int | None

class Run(BaseModel):
    accession: str | None              # DRR/SRR/ERR
    alias: str | None
    title: str | None
    run_date: str | None               # ISO 8601
    data_type: str | None              # JGA: "sequencing", "array", "metabolite", "image"
    data_blocks: list[DataBlock] | None
    attributes: list[Attribute] | None # RUN_ATTRIBUTES (TAG/VALUE)
    identifiers: list[Identifier] | None
    center_name: str | None
    broker_name: str | None
    run_center: str | None
    # experiment の値をこの run に限って上書きするもの
    platform: Platform | None
    spot_descriptor: SpotDescriptor | None
    processing: list[PipelineStep] | None
    sample_demux_directive: str | None
    legacy: RunLegacy | None

class RunLegacy(BaseModel):            # SRA XSD 1.5 より前の RUN の属性
    instrument_model: str | None       # PLATFORM の INSTRUMENT_MODEL とは別に書かれる
    instrument_name: str | None
    run_file: str | None
    total_data_blocks: int | None
```

設計上の決定:

- **名称 "run"**: SRA の用語を採用（"data" はあいまい）。JGA の "Data" は run に mapping
- **file type 統合**: SRA 31 enum + JGA 65+ enum を 1 つの `str` に統合、validation rule で制御
- **data_blocks**: SRA は file を DATA_BLOCK でまとめ、block ごとに名前や pool の member を持つ（1 つの run に複数ある）。file を平らな list にするとその区切りが失われる。JGA の DATA も DATA_BLOCK を 1 つ持つ形なので同じ型にする

## Analysis

SRA Analysis + JGA Analysis の統合。

```python
class StandardAssembly(BaseModel):
    short_name: str | None             # "GRCh38"
    names: list[ExternalRef] | None

class CustomAssembly(BaseModel):
    description: str | None
    sources: list[ExternalRef] | None

class RunLabel(BaseModel):             # read group とそれが来た run
    run: RelationTarget | None
    data_block_name: str | None
    read_group_label: str | None

class SeqLabel(BaseModel):             # 参照配列の名前とその配列
    accession: str | None
    gi: str | None
    data_block_name: str | None
    seq_label: str | None

class ReferenceAlignment(BaseModel):   # ANALYSIS_TYPE/REFERENCE_ALIGNMENT
    standard_assembly: StandardAssembly | None
    custom_assembly: CustomAssembly | None
    run_labels: list[RunLabel] | None
    seq_labels: list[SeqLabel] | None
    includes_unaligned_reads: bool | None
    marks_duplicate_reads: bool | None
    includes_failed_reads: bool | None

class Analysis(BaseModel):
    accession: str | None              # DRZ/SRZ/ERZ
    alias: str | None
    title: str | None
    description: str | None            # SRA/JGA DESCRIPTION
    analysis_type: str | None          # "de_novo_assembly", "microarray", ...
    analysis_date: str | None          # ISO 8601
    data_blocks: list[DataBlock] | None
    processing: list[PipelineStep] | None   # SRA PROCESSING/PIPELINE
    attributes: list[Attribute] | None # ANALYSIS_ATTRIBUTES (TAG/VALUE)
    identifiers: list[Identifier] | None
    center_name: str | None
    broker_name: str | None
    analysis_center: str | None
    reference_alignment: ReferenceAlignment | None
```

SRA 4 types + JGA 11+ types を 1 つの `str` に統合。validation rule で制御。

## Investigation (GEA)

GEA の experiment（E-GEAD）。MAGE-TAB の IDF と SDRF をそのままの形で持つ。写し方は [v3-gea.md](./v3-gea.md)。

```python
class ExperimentalFactor(BaseModel):   # IDF の Experimental Factor Name / Type の 1 組
    name: str | None
    type: str | None

class Protocol(BaseModel):             # IDF の Protocol Name / Type / Description（CIBEX の Protocol も）
    name: str | None                   # SDRF の Protocol REF から指される
    type: str | None
    description: str | None

class SdrfSource(BaseModel):
    name: str | None
    characteristics: list[Attribute] | None
    comments: list[Attribute] | None

class SdrfExtract(BaseModel):
    name: str | None
    protocol_refs: list[str] | None    # このノードの前に並ぶ Protocol REF
    material_type: str | None
    comments: list[Attribute] | None

class SdrfLabeledExtract(BaseModel):
    name: str | None
    protocol_refs: list[str] | None
    label: str | None
    comments: list[Attribute] | None

class SdrfAssay(BaseModel):
    name: str | None
    protocol_refs: list[str] | None
    technology_type: str | None
    array_design_ref: str | None
    comments: list[Attribute] | None

class SdrfDataFile(BaseModel):
    type: str | None                   # 列の名前（"Array Data File" など）
    name: str | None
    protocol_refs: list[str] | None
    comments: list[Attribute] | None

class SdrfFactorValue(BaseModel):      # Factor Value[name] と、その後の Unit[unit_type]
    name: str | None
    value: str | None
    unit: str | None
    unit_type: str | None

class SdrfRow(BaseModel):              # SDRF の 1 行
    source: SdrfSource | None
    extract: SdrfExtract | None
    labeled_extract: SdrfLabeledExtract | None
    assay: SdrfAssay | None
    data_files: list[SdrfDataFile] | None
    factor_values: list[SdrfFactorValue] | None

class CibexExperiment(BaseModel):
    title: str | None
    design_type: str | None
    factor: str | None
    common_reference: str | None
    quality_control_description: str | None
    number_of_hybridizations: int | None
    description: str | None

class CibexSubmitter(BaseModel):       # 住所・所属・研究室が自由記述で、Person / Organization に分けられない
    first_name: str | None
    middle_initials: str | None
    last_name: str | None
    organization: str | None
    department: str | None
    laboratory: str | None
    address: str | None

class CibexReference(BaseModel):       # 著者が 1 つの文字列、頁が 1 つの値で、Publication に写せない
    title: str | None
    author: str | None
    journal: str | None
    year: str | None
    volume: str | None
    issue: str | None
    page: str | None
    pubmed_id: str | None

class CibexDataField(BaseModel):       # データファイルの列の 1 つと、その説明
    field: str | None
    description: str | None

class CibexArrayDesign(BaseModel):
    accession: str | None              # CAR
    model_name: str | None
    technology_type: str | None
    surface_type: str | None
    number_of_features: int | None
    reporter_type: str | None
    strand_type: str | None
    substrate_type: str | None
    attachment: str | None
    design_provider: str | None
    array_design_protocol: str | None
    description: str | None
    file: str | None
    data_fields: list[CibexDataField] | None

class CibexSample(BaseModel):
    name: str | None
    organism: str | None
    organism_part: str | None
    sex: str | None
    age: str | None
    strain_or_line: str | None
    cell_line: str | None
    cell_type: str | None
    developmental_stage: str | None
    disease_state: str | None
    genetic_modification: str | None
    individual: str | None
    individual_genetic_characteristics: str | None
    growth_condition_protocol: str | None
    treatment_protocol: str | None
    biosource_provider: str | None
    description: str | None

class CibexLabeledExtract(BaseModel):
    label: str | None
    label_compound: str | None
    extraction_protocol: str | None
    labeling_protocol: str | None
    pooling_protocol: str | None

class CibexHybridization(BaseModel):
    name: str | None
    array_design_accession: str | None
    hybridization_protocol: str | None
    scanning_protocol: str | None
    description: str | None
    file: str | None
    data_fields: list[CibexDataField] | None

class CibexSummary(BaseModel):
    name: str | None
    normalization_protocol: str | None
    transformation_protocol: str | None
    description: str | None
    file: str | None
    data_fields: list[CibexDataField] | None

class Cibex(BaseModel):                # GEA に移す前の CIBEX の登録（CBX）
    accession: str | None
    release_date: str | None
    experiment: CibexExperiment | None
    submitters: list[CibexSubmitter] | None
    references: list[CibexReference] | None
    protocols: list[Protocol] | None
    array_designs: list[CibexArrayDesign] | None
    samples: list[CibexSample] | None
    labeled_extracts: list[CibexLabeledExtract] | None
    hybridizations: list[CibexHybridization] | None
    summaries: list[CibexSummary] | None

class InvestigationLegacy(BaseModel):  # CIBEX から移した experiment にだけあるもの
    cibex_accept_date: str | None
    cibex_public_release_date: str | None
    cibex_submitter: str | None
    cibex: Cibex | None

class Investigation(BaseModel):
    accession: str | None              # E-GEAD
    alias: str | None
    identifiers: list[Identifier] | None   # CIBEX の CBX は secondary
    title: str | None
    description: str | None
    magetab_version: str | None
    experimental_designs: list[str] | None
    experimental_factors: list[ExperimentalFactor] | None
    persons: list[Person] | None
    protocols: list[Protocol] | None
    publications: list[Publication] | None
    public_release_date: str | None
    sdrf_file: str | None
    sdrf: list[SdrfRow] | None
    # 以下は GEA が IDF の Comment[...] に書くもの
    experiment_type: str | None
    channel_type: str | None           # "single-channel", "dual-channel"
    array_design_ref: str | None       # SDRF の Array Design REF をまとめたもの
    last_update_date: str | None
    nbdc_approval: str | None          # NBDC のデータアクセス委員会の承認を述べる文
    dbcls_approval: str | None         # 同じく DBCLS
    legacy: InvestigationLegacy | None
```

設計上の決定:

- **SDRF は行ごと**: 同じ名前のノードを行の間で共有しない。保存された SDRF には、同じ名前のノードが行ごとに違う値を持つものがあり、共有すると失われる
- **BioProject / 関連する研究への参照**: IDF の `Comment[BioProject]`（`part_of`）と `Comment[Related study]`（`related_to`）は `relations` に置く。起点は `{"type": "investigation", "accession": ...}`
- **SDRF の中の参照は値のまま**: SDRF の `Comment[BioSample]`、`Comment[SRA_RUN]`、`Array Design REF` は BioSample や DRA、アレイ設計を指すが、relation にしない。relation の起点になれるのはオブジェクト（accession / alias / list の位置を持つもの）で、SDRF の行のノードはそうでない

## Array Design (GEA)

GEA のアレイ設計（A-GEAD）。ADF の見出しを型付きで持ち、プローブの表はファイルのまま指す。

```python
class TermSource(BaseModel):
    name: str | None
    file: str | None
    version: str | None

class ArrayDesignLegacy(BaseModel):
    cibex_public_release_date: str | None

class ArrayDesign(BaseModel):          # 見出しの欄は file の見出しから読んだもので、正本は file
    accession: str | None              # A-GEAD
    alias: str | None
    name: str | None
    version: str | None
    provider: str | None
    printing_protocol: str | None
    technology_type: str | None
    surface_type: str | None
    substrate_type: str | None
    sequence_polymer_type: str | None
    term_sources: list[TermSource] | None
    organism: Organism | None
    description: str | None
    public_release_date: str | None
    submitted_name: str | None
    file: File | None                  # ADF そのもの（プローブの表を含む）
    legacy: ArrayDesignLegacy | None
```

## Sequences & Entries

Trad / ST.26 固有のモデル。

```python
class Source(BaseModel):
    organism: Organism | None
    mol_type: str | None               # "genomic DNA"
    qualifiers: dict[str, list[Qualifier]] | None

class Entry(BaseModel):
    accession: str | None              # "AB123456.1" (version 含む)
    alias: str | None                  # submitter 指定 ID ("contig_001")
    name: str | None
    type: str | None                   # "chromosome", "plasmid", "unplaced", ...
    topology: str | None               # "circular", "linear"
    division: str | None               # GenBank division: "PLN", "BCT", "PAT", ...
    sequence: str | None
    comments: list[str] | None
    source_features: list[SourceFeature] | None

class StructuredComment(BaseModel):
    tagset_id: str | None              # "Genome-Assembly-Data", "FluData", ...
    fields: dict[str, str] | None

class Sequences(BaseModel):
    seq_prefix: str | None
    common_source: Source | None
    entries: list[Entry] | None
    structured_comments: list[StructuredComment] | None
    attributes: list[Attribute] | None
```

ST_COMMENT（Structured Comment）は Trad 固有の概念。21+ 種のブロック型、150-200+ の key field が存在するため EAV（`dict[str, str]`）で保持。v2 の `experiments[].experiment_attributes` から移動。

大規模ゲノムでは JSON ファイルサイズが数 GB になりうるため、配列本体の外部ファイル参照や streaming parse の必要性は実装フェーズで評価する。

## Features

INSDC feature table に基づくアノテーション。

```python
class Qualifier(BaseModel):
    alias: str | None                  # ローカル識別子
    value: str | None

class Feature(BaseModel):
    alias: str | None                  # ローカル識別子（GFF の ID 属性に相当）
    type: str | None                   # "CDS", "gene", "rRNA", ...
    location: str | None               # INSDC location format
    sequence_id: str | None            # Entry.alias への参照
    qualifiers: dict[str, list[Qualifier]] | None
    locus_tag_id: str | None
    source_tool: str | None            # GFF source 列（どのツールが予測したか）
    score: float | None                # GFF score 列（予測信頼度）
    phase: int | None                  # GFF phase 列 (0, 1, 2)
    parent_ids: list[str] | None       # GFF Parent 属性（親 Feature の alias 参照）
```

設計上の決定:

- Feature / Qualifier は accession を持たない。alias のみで識別する
- Feature は type + location でも識別可能（CDS は領域の重複を許容しないため composite key として機能）
- `source_tool` / `score` は GFF 由来の情報を保持するためのフィールド。GFF 以外の入力では None
- `phase` は GFF の 8 列目（CDS のリーディングフレーム、0/1/2）。INSDC の codon_start qualifier と相互変換可能（phase=0 → codon_start=1）
- `parent_ids` は GFF の Parent 属性。feature 階層（gene → mRNA → CDS）をローカルに表現する。GFF3 は複数 Parent を許容するため `list[str]`
- protein_id の付与は alias を参照先として行う

## Assembly

```python
class Assembly(BaseModel):
    accession: str | None              # GCA_/GCF_ (version 含む)
    alias: str | None
    title: str | None                  # ENA Assembly TITLE
    name: str | None                   # assembly name（グローバル名）
    description: str | None            # ENA Assembly DESCRIPTION
    assembly_level: str | None         # "complete genome", "chromosome", "scaffold", "contig"
    genome_representation: str | None  # "full", "partial"
    attributes: list[Attribute] | None # ASSEMBLY_ATTRIBUTES (TAG/VALUE: n50, total-length, ...)
```

設計上の決定:

- **Chromosome モデルを廃止**: Entry が既に name, type, topology を持つ。「この Entry は chromosome 1」という情報は Entry 自身で表現し、二重管理を避ける
- **submission_category を削除**: 判別フィールドを持たない方針に従い、変換元の分類情報は `provenance` に格納する
- ST_COMMENT 由来の Assembly Method, Genome Coverage 等は `Sequences.structured_comments` に格納

## Dataset

JGA 固有。独立したトップレベル���念。Run/Analysis/Policy への参照は `relations` で表現。

```python
class Dataset(BaseModel):
    accession: str | None              # JGAD
    alias: str | None
    title: str | None
    description: str | None
    dataset_types: list[str] | None    # "Exome sequencing", "Genotyping by array", ...
    attributes: list[Attribute] | None
```

## Access Control

JGA 固有。Policy と DAC を `access_control` にネスト。

```python
class Policy(BaseModel):
    accession: str | None              # JGAP
    alias: str | None
    title: str | None
    policy_text: str | None
    policy_url: str | None
    attributes: list[Attribute] | None

class Dac(BaseModel):
    accession: str | None              # JGAC
    alias: str | None
    contacts: list[Person] | None
    attributes: list[Attribute] | None

class AccessControl(BaseModel):
    policy: Policy | None
    dac: Dac | None
```

## Relations

外部参照（URL, db_xref）と意味的関係を統合。旧 Links と旧 Relations を統一。

### 型定義

```python
class RelationSource(BaseModel):
    type: str | None                   # "sample", "project", "experiment", "investigation", ...
    alias: str | None
    accession: str | None              # あれば alias より先にこちらで指す（SRA の alias は一意でない）
    index: int | None                  # accession も一意な alias も無いとき、その種類の list の中の位置

class RelationTarget(BaseModel):
    url: str | None                    # URL 参照の場合
    db: str | None                     # DB 参照 / record 内参照
    id: str | None                     # DB 参照ならその DB の番号、オブジェクト参照なら alias
    accession: str | None              # オブジェクト参照で、相手の accession も書くとき
    center_name: str | None            # alias の名前空間（SRA の refcenter）
    identifiers: list[Identifier] | None

class Relation(BaseModel):
    type: str | None                   # "reference", "xref", "child_of", "derived_from", "part_of", ...
    source: RelationSource | None      # record 内の起点（省略時は record 全体）
    target: RelationTarget | None
    label: str | None                  # 表示名
    properties: dict[str, str] | None
```

設計上の決定:

- **Links と Relations を統合**: 外部 web 参照、外部 DB 参照、意味的関係は全て広義の relation
- `type` で用途を区別: `"reference"` (URL), `"xref"` (db_xref), `"child_of"`, `"derived_from"` 等
- `RelationTarget` に `url` / `db` + `id` を統合。URL が入っていれば外部参照、db + id が入っていれば DB/record 内参照
- `source` は record 内のどのオブジェクトからの関係かを示す。省略時は record 全体が起点
- SRA の参照は refname（alias）と accession を同時に書ける。オブジェクト参照では `id` に alias、`accession` に accession を置き、どちらか一方に寄せない
- `db` がオブジェクトの種類のとき、相手がこの record の中にあるかどうかは表さない。読む側が accession か (center_name, alias) で探す
- record 内参照（Experiment → Sample, Run → Experiment 等）も `relations` で統一的に表現
- **set 内 record 間参照**: 1 submit で複数 record を送る場合、alias 参照解決は 2 フェーズ（submit 時に namespace 付与 → 参照解決）を想定

### relation type 一覧

| type | 意味 | 主な用途 |
|------|------|---------|
| `reference` | 外部 URL 参照 | Web ページへのリンク |
| `xref` | 外部 DB 相互参照 | PubMed, BioProject accession 等 |
| `part_of` | 起点が対象の一部である | SRA Experiment → Sample, Run → Experiment |
| `child_of` | 起点が対象の子である | Umbrella BioProject の親子関係 |
| `derived_from` | 起点が対象から派生した | BioSample の派生関係（培養株 → 元株）、SRA Analysis の TARGETS |
| `governed_by` | 起点が対象のポリシーに従う | JGA Dataset → Policy |
| `managed_by` | 起点が対象に管理される | JGA Policy → DAC |
| `contains` | 起点が対象を含む | JGA Dataset → Run/Analysis |
| `related_to` | 起点が対象に関係する | SRA STUDY の RELATED_STUDIES（`properties.is_primary`） |

### 使用例

```jsonc
// Web 参照（旧 Link）
{"type": "reference", "target": {"url": "https://example.com"}, "label": "Project homepage"}

// DB 相互参照（旧 Link の db_xref）
{"type": "xref", "target": {"db": "pubmed", "id": "12345678"}}

// record 内参照
{"type": "part_of", "source": {"type": "experiment", "alias": "exp-1"}, "target": {"db": "sample", "id": "sample-1"}}

// 親子関係
{"type": "child_of", "target": {"db": "bioproject", "id": "PRJDB00001"}}
```

### 実例

#### SRA record 内参照（Experiment → Sample, Run → Experiment）

SRA の典型的なオブジェクトグラフ。1 record 内で Experiment が Sample を、Run が Experiment を参照する。

```json
{
  "samples": [
    {"accession": "SAMD00000001", "alias": "sample-1", "title": "Human liver sample"}
  ],
  "experiments": [
    {"accession": "DRX000001", "alias": "exp-1", "title": "RNA-seq experiment"}
  ],
  "runs": [
    {"accession": "DRR000001", "alias": "run-1", "title": "Sequencing run 1"}
  ],
  "relations": [
    {
      "type": "part_of",
      "source": {"type": "experiment", "accession": "DRX000001"},
      "target": {"db": "sample", "id": "sample-1", "accession": "SAMD00000001"}
    },
    {
      "type": "part_of",
      "source": {"type": "run", "accession": "DRR000001"},
      "target": {"db": "experiment", "id": "exp-1", "accession": "DRX000001"}
    }
  ]
}
```

XSD 対応: `EXPERIMENT/SAMPLE_DESCRIPTOR`, `RUN/EXPERIMENT_REF`。起点は accession で指し、target には参照に書かれた refname（`id`）と accession を両方置く（[v3-sra.md](./v3-sra.md)）

#### SRA Analysis → Study 参照

```json
{
  "project": {
    "accession": "DRP000001",
    "alias": "my-study",
    "identifiers": [{"type": "primary", "value": "PRJDB12345", "label": "BioProject ID"}]
  },
  "analyses": [
    {"accession": "DRZ000001", "alias": "analysis-1", "analysis_type": "de_novo_assembly"}
  ],
  "relations": [
    {
      "type": "part_of",
      "source": {"type": "analysis", "accession": "DRZ000001"},
      "target": {"db": "project", "id": "my-study", "accession": "DRP000001"}
    }
  ]
}
```

XSD 対応: `ANALYSIS/STUDY_REF`。DRA の study の accession は DRP で、BioProject の番号は `PRIMARY_ID` に書かれる

#### Umbrella BioProject の親子関係

1 record = 1 Project。子 project の record から親を参照する。

```json
{
  "project": {
    "accession": "PRJDB99999",
    "title": "Genome sequencing of bacterial strains",
    "project_type": "primary"
  },
  "relations": [
    {
      "type": "child_of",
      "target": {"db": "bioproject", "id": "PRJDB00001"}
    }
  ]
}
```

source を省略すると record 全体が起点となる。record が単一の project のみを含む場合に簡潔に書ける。

#### BioSample の派生関係（derived_from）

培養株や処理後サンプルが元サンプルから派生した関係。

```json
{
  "samples": [
    {"accession": "SAMD00000010", "alias": "derived-sample", "title": "Cultured strain"}
  ],
  "relations": [
    {
      "type": "derived_from",
      "source": {"type": "sample", "alias": "derived-sample"},
      "target": {"db": "biosample", "id": "SAMD00000001"}
    }
  ]
}
```

XSD 対応: BioSample XSD の `Relations/derived_from`

#### JGA controlled-access chain（Dataset → Policy → DAC）

JGA 固有のアクセス制御チェーン。

```json
{
  "datasets": [
    {"accession": "JGAD000001", "alias": "dataset-1", "title": "Exome data"}
  ],
  "access_control": {
    "policy": {
      "accession": "JGAP000001",
      "alias": "policy-1",
      "title": "Data access policy"
    },
    "dac": {
      "accession": "JGAC000001",
      "alias": "dac-1"
    }
  },
  "relations": [
    {
      "type": "governed_by",
      "source": {"type": "dataset", "alias": "dataset-1"},
      "target": {"db": "jga.policy", "id": "JGAP000001"}
    },
    {
      "type": "managed_by",
      "source": {"type": "policy", "alias": "policy-1"},
      "target": {"db": "jga.dac", "id": "JGAC000001"}
    },
    {
      "type": "contains",
      "source": {"type": "dataset", "alias": "dataset-1"},
      "target": {"db": "jga.analysis", "id": "JGAR000001"}
    }
  ]
}
```

XSD 対応: `DATASET/POLICY_REF`, `POLICY/DAC_REF`

#### 複数 Sample を持つ record 内の個別参照

```json
{
  "samples": [
    {"alias": "tumor-sample", "title": "Tumor tissue"},
    {"alias": "normal-sample", "title": "Normal tissue"}
  ],
  "experiments": [
    {"alias": "tumor-exp", "title": "Tumor RNA-seq"},
    {"alias": "normal-exp", "title": "Normal RNA-seq"}
  ],
  "relations": [
    {
      "type": "part_of",
      "source": {"type": "experiment", "alias": "tumor-exp"},
      "target": {"db": "sample", "id": "tumor-sample"}
    },
    {
      "type": "part_of",
      "source": {"type": "experiment", "alias": "normal-exp"},
      "target": {"db": "sample", "id": "normal-sample"}
    }
  ]
}
```

#### properties 付き relation

追加情報が必要な場合に `properties` を使う。

```json
{
  "relations": [
    {
      "type": "part_of",
      "source": {"type": "sample", "alias": "sample-1"},
      "target": {"db": "bioproject", "id": "PRJDB12345"},
      "properties": {
        "registration_date": "2025-01-15",
        "note": "Added in second batch"
      }
    }
  ]
}
```

### 典型的な登録パターンごとの relations

| パターン | 割合 | relations の特徴 |
|----------|------|-----------------|
| BP only (47.0%) | 通常不要。umbrella の子の場合のみ `child_of` |
| BP + BS + SRA (33.8%) | Experiment → Sample, Run → Experiment の `part_of` |
| BP + BS + SRA + Trad (6.7%) | 上記に加え、assembly → project の参照がありうる |
| BP + BS + Trad (6.4%) | 通常は relations 不要（project/sample は `xref` で参照） |
| BP + BS (5.3%) | 通常不要 |

## Provenance

data の来歴記録。変換元形式やツール情報を typed フィールドで保持する。

```python
class GffMeta(BaseModel):
    version: str | None                # GFF version ("3")
    pragmas: list[str] | None          # ["##sequence-region chr1 1 2000000"]
    source_tool: str | None            # GFF source 列のデフォルト値（"DFAST" 等）

class Provenance(BaseModel):
    source_format: str | None          # "GFF", "trad", "SRA", ...
    submission_category: str | None    # 変換元の分類情報（"WGS", "GNM", "MAG" 等）
    gff: GffMeta | None                # GFF 固有の来歴情報
```

設計上の決定:

- `extra="allow"` は将来の拡張用に残すが、既知の情報は typed フィールドで保持する
- `submission_category` は判別フィールドを持たない方針に従い、record のトップレベルではなく provenance に格納
- GFF 固有の per-feature 情報（source_tool, score）は Feature のフィールドとして保持し、provenance には record レベルの GFF メタデータのみ格納

