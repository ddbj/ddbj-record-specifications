# v3 スキーマ仕様

DDBJ Record v3 のデータモデル定義。
全形式（Trad, BP, BS, SRA, JGA, ST.26, GFF, Assembly）を統一的に扱う JSON フォーマットを定義する。

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

GEA, MetaboBank, JVar は現在スコープ外。将来の拡張候補。

## Top-level 構造

```
DdbjRecord (all fields Optional/None)
├── schema_version: str
├── provenance: Provenance | None       # data の来歴記録（変換元形式、GFF メタデータ等）
├── submission: Submission | None       # submitters, hold_date, comments, st26
├── project: Project | None             # = BP + SRA Study + JGA Study
│   ├── name, project_type              # BP Name (短縮名), "primary"/"umbrella"
│   ├── umbrella_subtype                # umbrella 固有の subtype
│   ├── study_types                     # "WGS", "Case-Control", ...
│   ├── publications, grants, keywords, relevance
│   ├── locus_tag_prefix
│   └── target                          # sample_scope, material, capture, method, data_types
├── samples: list[Sample] | None        # = BS + SRA Sample + JGA Sample (EAV)
├── experiments: list[Experiment] | None # SRA/JGA experiment (library, platform)
├── runs: list[Run] | None              # SRA Run + JGA Data (files)
├── analyses: list[Analysis] | None     # SRA/JGA analysis (analysis_type, files)
├── sequences: Sequences | None         # Trad/ST.26 (entries, common_source)
├── features: list[Feature] | None      # INSDC feature table
├── assembly: Assembly | None           # assembly accession, name, level
├── datasets: list[Dataset] | None      # JGA Dataset（独立）
├── relations: list[Relation] | None    # 外部参照 (URL, db_xref) + 意味的関係 (child_of, ...)
└── access_control: AccessControl | None # JGA Policy/DAC
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

### accession / alias

各モデルに持たせる識別子フィールド。

```python
# Project, Sample, Experiment, Run, Analysis, Entry, Dataset, Assembly,
# Policy, Dac に共通:
accession: str | None         # 登録後に付与 ("PRJDB12345", "SAMD00123456", ...)
alias: str | None             # 登録前のローカル名 (SRA refname 等)

# Feature, Qualifier:
alias: str | None             # ローカル識別子（accession は持たない）
```

- 登録前は alias のみ、登録後に accession が追記される
- alias は submission (record) 内で unique
- submit 時に submission_id が namespace になる（例: `<submission_id>::bioproject::my-project-01`）
- center_name は submission.submitters の Organization から導出可能なため含めない
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

class Submission(BaseModel):
    submitters: list[Person] | None   # submitters[0] = contact person
    hold_date: str | None             # ISO 8601
    comments: list[str] | None        # free-form notes
    st26: St26Meta | None             # ST.26 特許メタデータ
    attributes: list[Attribute] | None
```

v2 submission にあった references, keywords, locus_tag_prefix, division, db_xrefs 等は適切な帰属先に移動済み。

設計上の決定:

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
```

設計上の決定:

- **project_type と study_types を分離**: BP の構造種別（primary/umbrella）と SRA/JGA の研究手法/デザインは別概念
- **Umbrella**: 1 JSON = 1 Project。umbrella は `project_type: "umbrella"` ��表現し、親子関係は `relations` で
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
    name: str | None
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
```

設計上の決定:

- **EAV 維持**: BioSample の ~960 attributes を全て typed fields にするのは非現実的。validation rule で必須/任意を制御
- **common_source との関係**: 統合しない。Sample.organism と Sequences.common_source は役割が異なる（試料メタデータ vs INSDC source feature のデフォルト値）。整合性は validation rule で検証
- **collection_date**: attributes のまま（昇格させるとキリがない）
- **anonymized_name**: attributes で扱う

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

class Platform(BaseModel):
    type: str | None                   # "ILLUMINA", "PACBIO_SMRT", ...
    instrument_model: str | None       # "Illumina HiSeq 2500", ...
    array_name: str | None             # JGA array の場合
    array_description: str | None      # JGA array の場合
    array_provider: str | None         # JGA array の場合

class ReadSpec(BaseModel):
    read_index: int | None
    read_class: str | None             # "Application Read", "Technical Read", ...
    read_type: str | None              # "Forward", "Reverse", ...
    base_coord: int | None

class SpotDescriptor(BaseModel):
    spot_length: int | None
    reads: list[ReadSpec] | None

class PipelineStep(BaseModel):
    step_index: str | None
    prev_step_index: str | None        # "NIL" for first step
    program: str | None
    version: str | None

class Experiment(BaseModel):
    accession: str | None              # DRX/SRX/ERX
    alias: str | None
    title: str | None
    description: str | None            # SRA DESIGN_DESCRIPTION
    library: LibraryDescriptor | None
    platform: Platform | None
    targeted_loci: list[str] | None    # "16S rRNA", "exome", ...
    spot_descriptor: SpotDescriptor | None  # SRA SPOT_DESCRIPTOR
    processing: list[PipelineStep] | None   # SRA PROCESSING/PIPELINE
    attributes: list[Attribute] | None # EXPERIMENT_ATTRIBUTES (TAG/VALUE)
```

設計上の決定:

- **controlled vocabulary**: 全て `str | None`。許容値は YAML 外部定義 + validation rule で制御（XSD enum は頻繁に更新される���め）
- **JGA array platform**: Platform に flat に統合

## Run

SRA Run + JGA Data の統合。

```python
class File(BaseModel):
    filename: str | None
    filetype: str | None               # "fastq", "bam", "cram", "CEL", ...
    checksum_method: str | None        # "MD5"
    checksum: str | None
    unencrypted_checksum: str | None   # JGA: checksum before encryption

class Run(BaseModel):
    accession: str | None              # DRR/SRR/ERR
    alias: str | None
    title: str | None
    run_date: str | None               # ISO 8601
    data_type: str | None              # JGA: "sequencing", "array", "metabolite", "image"
    files: list[File] | None
    attributes: list[Attribute] | None # RUN_ATTRIBUTES (TAG/VALUE)
```

設計上の決定:

- **名称 "run"**: SRA の用語を採用（"data" はあいまい）。JGA の "Data" は run に mapping
- **file type 統合**: SRA 31 enum + JGA 65+ enum を 1 つの `str` に統合、validation rule で制御

## Analysis

SRA Analysis + JGA Analysis の統合。

```python
class Analysis(BaseModel):
    accession: str | None              # DRZ/SRZ/ERZ
    alias: str | None
    title: str | None
    description: str | None            # SRA/JGA DESCRIPTION
    analysis_type: str | None          # "de_novo_assembly", "microarray", ...
    analysis_date: str | None          # ISO 8601
    files: list[File] | None           # File 型を再利用
    processing: list[PipelineStep] | None   # SRA PROCESSING/PIPELINE
    attributes: list[Attribute] | None # ANALYSIS_ATTRIBUTES (TAG/VALUE)
```

SRA 4 types + JGA 11+ types を 1 つの `str` に統合。validation rule で制御。

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
    type: str | None                   # "sample", "project", "experiment", ...
    alias: str | None

class RelationTarget(BaseModel):
    url: str | None                    # URL 参照の場合
    db: str | None                     # DB 参照 / record 内参照
    id: str | None                     # DB 参照 / record 内参照

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
- record 内参照（Experiment → Sample, Run → Experiment 等）も `relations` で統一的に表現
- **set 内 record 間参照**: 1 submit で複数 record を送る場合、alias 参照解決は 2 フェーズ（submit 時に namespace 付与 → 参照解決）を想定

### relation type 一覧

| type | 意味 | 主な用途 |
|------|------|---------|
| `reference` | 外部 URL 参照 | Web ページへのリンク |
| `xref` | 外部 DB 相互参照 | PubMed, BioProject accession 等 |
| `part_of` | 起点が対象の一部である | SRA Experiment → Sample, Run → Experiment |
| `child_of` | 起点が対象の子である | Umbrella BioProject の親子関係 |
| `derived_from` | 起点が対象から派生した | BioSample の派生関係（培養株 → 元株） |
| `governed_by` | 起点が対象のポリシーに従う | JGA Dataset → Policy |
| `managed_by` | 起点が対象に管理される | JGA Policy → DAC |
| `contains` | 起点が対象を含む | JGA Dataset → Run/Analysis |

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
      "source": {"type": "experiment", "alias": "exp-1"},
      "target": {"db": "sample", "id": "sample-1"}
    },
    {
      "type": "part_of",
      "source": {"type": "run", "alias": "run-1"},
      "target": {"db": "experiment", "id": "exp-1"}
    }
  ]
}
```

XSD 対応: `EXPERIMENT/SAMPLE_DESCRIPTOR`, `RUN/EXPERIMENT_REF`

#### SRA Analysis → Study 参照

```json
{
  "project": {"accession": "PRJDB12345", "alias": "my-project"},
  "analyses": [
    {"accession": "DRZ000001", "alias": "analysis-1", "analysis_type": "de_novo_assembly"}
  ],
  "relations": [
    {
      "type": "part_of",
      "source": {"type": "analysis", "alias": "analysis-1"},
      "target": {"db": "bioproject", "id": "PRJDB12345"}
    }
  ]
}
```

XSD 対応: `ANALYSIS/STUDY_REF`

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

