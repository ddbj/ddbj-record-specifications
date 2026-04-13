# v3 設計議論

DDBJ Record v3 の設計に関する議論ノート。
全形式（Trad, BP, BS, SRA, JGA, ST.26, GFF, Assembly）を統一的に扱える JSON フォーマットを、1 から設計する。

## 方針

- 設計アプローチ: 案 E（flat + validation rules）を採用（[extension-and-validation-design.md](./extension-and-validation-design.md) 参照）
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
| ST.26 | DDBJ (PAT division) | 特許配列リスト |
| GFF | DDBJ | ゲノムアノテーション |
| Assembly | DDBJ + NCBI | NCBI Assembly 登録、accession、index 生成 |

## 確定したデータモデル

### Top-level 構造

```
DdbjRecord (all fields Optional/None)
├── schema_version: str
├── provenance: Provenance | None       # data の来歴記録（変換元形式、GFF メタデータ等）
├── submission: Submission | None       # thin: submitters, hold_date, comments only
├── project: Project | None             # = BP + SRA Study + JGA Study
│   ├── project_type                    # "primary", "umbrella"
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

- **案 E の徹底**: 全フィールド `T | None`。record_type のような判別フィールドは不要。validation rules の通過結果から「何として有効か」を導出する
- **段階的更新**: 1 つの record ファイルを段階的に更新していく運用モデル（project 登録 → accession 追記 → sample 追記 → ...）
- **submission set**: 1 つの DdbjRecord に複数 DB の情報を含めることで、submission set を自然に表現
- **status**: record に含めない。record-idm の外部メタデータ
- **ObjectType 基底モデル**: 作らない。accession, alias 等は各モデルが個別に持つ
- **GFF トップレベル廃止**: GFF は入力フォーマットであり record の構成要素ではない。features に正規化し、GFF 固有情報は provenance に退避
- **Links と Relations の統合**: 外部参照（URL, db_xref）も意味的関係も広義の relation として `relations` に統合。旧 `links` フィールドは廃止
- **submission_category**: record_type / 判別フィールドに該当するため、モデルに持たない（Option E 原則）。変換元の分類情報は provenance に格納

### 共通型

#### Organism

Project, Sample, Sequences (common_source) で横断的に使われる。最小限のフィールドに絞る（strain, isolate 等は Sample attributes (EAV) で扱う）。

```python
class Organism(BaseModel):
    name: str | None              # "Homo sapiens"
    taxonomy_id: int | None       # NCBI Taxonomy ID (e.g., 9606)
```

#### Date

型は `str | None`。ISO 8601 形式で精度のバリエーションを許容（`"2024-01-15T09:00:00Z"`, `"2024-01-15"`, `"2024-01"`, `"2024"`）。形式の検証は validation rule で行う。submitter 指定の date のみ record に含め、archive 管理の日付（created, modified, published 等）は外部メタデータ。

#### Person / Organization / Address

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

#### accession / alias

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

### Submission

提出行為のメタデータに限定する（thin submission）。

```python
class Submission(BaseModel):
    submitters: list[Person] | None   # submitters[0] = contact person
    hold_date: str | None             # ISO 8601
    comments: list[str] | None        # free-form notes
```

v2 submission にあった references, keywords, locus_tag_prefix, division, db_xrefs 等は適切な帰属先に移動済み。

### Project

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

class Grant(BaseModel):
    title: str | None
    agency: str | None
    id: str | None

# grant の URI

class ProjectTarget(BaseModel):
    sample_scope: str | None           # "monoisolate", "multispecies", "environment", ...
    material: str | None               # "genome", "transcriptome", "proteome", ...
    capture: str | None                # "whole", "exome", "targeted_locus", ...
    method: str | None                 # "sequencing", "array", "mass_spec", ...
    data_types: list[str] | None       # "raw_sequence_reads", "assembly", "annotation", ...

class Project(BaseModel):
    accession: str | None              # PRJDB/PRJNA/PRJEB
    alias: str | None
    title: str | None
    description: str | None
    project_type: str | None           # "primary", "umbrella"
    study_types: list[str] | None      # "WGS", "Case-Control", ...
    organism: Organism | None
    publications: list[Publication] | None
    grants: list[Grant] | None
    keywords: list[str] | None
    relevance: dict[str, str] | None   # {"agricultural": "crop improvement", ...}
    locus_tag_prefix: list[str] | None
    target: ProjectTarget | None
```

設計上の決定:

- **project_type と study_types を分離**: BP の構造種別（primary/umbrella）と SRA/JGA の研究手法/デザインは別概念
- **Umbrella**: 1 JSON = 1 Project。umbrella は `project_type: "umbrella"` で表現し、親子関係は `relations` で
- **target**: BP ProjectTypeSubmission 固有の概念を `ProjectTarget` としてネスト
- **division**: project には含めない（Entry レベル or validator 導出）
- **datatype**: project には含めない（assembly.submission_category に統合）
- **relevance**: BP XSD の Relevance は string 値を持てるため `dict[str, str]` で保持

### Sample

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

### Experiment

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

class Experiment(BaseModel):
    accession: str | None              # DRX/SRX/ERX
    alias: str | None
    title: str | None
    library: LibraryDescriptor | None
    platform: Platform | None
    targeted_loci: list[str] | None    # "16S rRNA", "exome", ...
```

設計上の決定:

- **controlled vocabulary**: 全て `str | None`。許容値は YAML 外部定義 + validation rule で制御（XSD enum は頻繁に更新されるため）
- **JGA array platform**: Platform に flat に統合

### Run

SRA Run + JGA Data の統合。

```python
class File(BaseModel):
    filename: str | None
    filetype: str | None               # "fastq", "bam", "cram", "CEL", ...
    checksum_method: str | None        # "MD5"
    checksum: str | None

class Run(BaseModel):
    accession: str | None              # DRR/SRR/ERR
    alias: str | None
    title: str | None
    run_date: str | None               # ISO 8601
    data_type: str | None              # JGA: "sequencing", "array", "metabolite", "image"
    files: list[File] | None
```

設計上の決定:

- **名称 "run"**: SRA の用語を採用（"data" はあいまい）。JGA の "Data" は run に mapping
- **file type 統合**: SRA 31 enum + JGA 65+ enum を 1 つの `str` に統合、validation rule で制御

### Analysis

SRA Analysis + JGA Analysis の統合。

```python
class Analysis(BaseModel):
    accession: str | None              # DRZ/SRZ/ERZ
    alias: str | None
    title: str | None
    analysis_type: str | None          # "de_novo_assembly", "microarray", ...
    analysis_date: str | None          # ISO 8601
    files: list[File] | None           # File 型を再利用
```

SRA 4 types + JGA 11+ types を 1 つの `str` に統合。validation rule で制御。

### Sequences & Entries

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
```

ST_COMMENT（Structured Comment）は Trad 固有の概念。21+ 種のブロック型、150-200+ の key field が存在するため EAV（`dict[str, str]`）で保持。v2 の `experiments[].experiment_attributes` から移動。

### Features

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
```

設計上の決定:

- Feature / Qualifier は accession を持たない。alias のみで識別する
- Feature は type + location でも識別可能（CDS は領域の重複を許容しないため composite key として機能）
- `source_tool` / `score` は GFF 由来の情報を保持するためのフィールド。GFF 以外の入力では None
- protein_id の付与は alias を参照先として行う

### Assembly

```python
class Assembly(BaseModel):
    accession: str | None              # GCA_/GCF_ (version 含む)
    alias: str | None
    name: str | None                   # assembly name（グローバル名）
    assembly_level: str | None         # "complete genome", "chromosome", "scaffold", "contig"
    genome_representation: str | None  # "full", "partial"
```

設計上の決定:

- **Chromosome モデルを廃止**: Entry が既に name, type, topology を持つ。「この Entry は chromosome 1」という情報は Entry 自身で表現し、二重管理を避ける
- **submission_category を削除**: Option E 原則（判別フィールドを持たない）に従い、変換元の分類情報は `provenance` に格納する
- ST_COMMENT 由来の Assembly Method, Genome Coverage 等は `Sequences.structured_comments` に格納

### Dataset

JGA 固有。独立したトップレベル概念。Run/Analysis/Policy への参照は `relations` で表現。

```python
class Dataset(BaseModel):
    accession: str | None              # JGAD
    alias: str | None
    title: str | None
    description: str | None
    dataset_types: list[str] | None    # "Exome sequencing", "Genotyping by array", ...
```

### Access Control

JGA 固有。Policy と DAC を `access_control` にネスト。

```python
class Policy(BaseModel):
    accession: str | None              # JGAP
    alias: str | None
    title: str | None
    policy_text: str | None
    policy_url: str | None

class Dac(BaseModel):
    accession: str | None              # JGAC
    alias: str | None
    contacts: list[Person] | None

class AccessControl(BaseModel):
    policy: Policy | None
    dac: Dac | None
```

### Relations

外部参照（URL, db_xref）と意味的関係を統合。旧 Links と旧 Relations を統一。

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

使用例:

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

### Provenance

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
- `submission_category` は Option E 原則（判別フィールドを持たない）に従い、record のトップレベルではなく provenance に格納
- GFF 固有の per-feature 情報（source_tool, score）は Feature のフィールドとして保持し、provenance には record レベルの GFF メタデータのみ格納

## Validation rule 実装リファレンス

### Validation 機構の設計

eslint のアーキテクチャを参考にした設計。

**原則: record は純粋な data。validation config は外付け。**

```
record.json          -> pure data (what)
rules (Python)       -> validation logic (check + fix)
config (CLI/API)     -> which rules to run, at what severity (how)
```

**Rule の Python interface:**

```python
class Rule(Protocol):
    id: str                          # "bp/title-required"
    default_severity: Severity       # error / warning

    def check(self, record, context) -> list[Diagnostic]: ...
    def fix(self, record, diagnostic) -> Record | None: ...  # optional
```

**Rule の構成:**

```
This repo (ddbj-record-specifications)
├── Rules (individual, Python interface)
│   ├── bp/title-required
│   ├── bp/organism-required
│   ├── bs/attributes-required
│   ├── sra/library-strategy-valid
│   ├── insdc/feature-key-exists
│   └── ...
├── Rule sets (convenience groupings)
│   ├── BP_RULES, BS_RULES, SRA_RULES, INSDC_RULES, ALL_RULES
│   └── BP_SUBMISSION_RULES
└── Rule definitions (YAML data, loaded by Python rules)
    ├── insdc_feature_table.yaml
    ├── bs_packages.yaml
    └── ...
```

**Consumer による自由な組み合わせ:**

```python
# Python API
from ddbj_record.rules import BP_RULES, BS_RULES
results = validate(record, rules=BP_RULES + BS_RULES, stage="draft")

# CLI
ddbj-record validate --rules bp,bs --stage draft record.json
ddbj-record validate --rules bp,bs --stage draft --fix record.json
```

**rule と config の責務分離:**

| 責務 | 担当 | 例 |
|------|------|-----|
| rule の定義 | this repo | `bp/title-required`, `insdc/feature-key-exists` |
| rule set の定義 | this repo | `BP_RULES`, `SRA_RULES` |
| どの rule を使うか | consumer (API / CLI / other tools) | `--rules bp,bs` |
| どの stage で検証するか | consumer | `--stage draft` |
| severity の override | consumer | `--severity bp/title-required=warning` |

### Validation の段階的挙動

| stage | 例 | validation の期待 |
|-------|-----|-------------------|
| draft | submitter がローカルで作成 | 緩い（warning 中心） |
| submission | DDBJ に提出 | 厳密（error で reject） |
| curation | DDBJ staff が編集 | 厳密 + 追加ルール |
| accepted | accession 発行済み | 変更制約あり |
| public | 外部公開済み | validation skip or 読み取り専用 |

### Fix の設計

`--fix` で自動修正可能な操作の分類:

| fix の種類 | 例 | 安全性 |
|-----------|-----|--------|
| 正規化 | 日付フォーマット統一、空白 trim | 安全 |
| 導出 | organism → division 自動決定 | やや安全（taxonomy DB 依存） |
| デフォルト補完 | 欠落フィールドにデフォルト値 | 要注意 |
| 構造変換 | v2 → v3 マイグレーション | converter の責務 |
| curation | qualifier value の修正、organism 名の正規化 | 外部リソース依存 |

### 各形式との対応表

v3 モデルと各形式のフィールド対応。converter / validation rule 実装時に参照する。

#### Project

| v3 | BP | SRA Study | JGA Study |
|----|----|----|-----|
| title | Title | STUDY_TITLE | STUDY_TITLE |
| description | Description | STUDY_ABSTRACT | STUDY_ABSTRACT |
| project_type | TopSingle="primary", TopAdmin="umbrella" | - | - |
| study_types | - | STUDY_TYPE (1 値) | STUDY_TYPES (複数値) |
| organism | Organism | - (Sample 側) | - (Sample 側) |
| publications | Publication (StructuredCitation) | STUDY_LINKS (PubMed xref) | PUBLICATIONS |
| grants | Grant | - | GRANTS |
| keywords | Keyword | - | - |
| relevance | Relevance (6+1 categories) | - | - |
| locus_tag_prefix | LocusTagPrefix | - | - |
| target.* | Target (sample_scope/material/capture) + Method + Objectives | - | - |

#### Sample

| v3 | BioSample | SRA Sample | JGA Sample |
|----|-----------|-----------|-----------|
| title | Title | TITLE | TITLE |
| organism | Organism (taxonomy_id, OrganismName) | SAMPLE_NAME (TAXON_ID, SCIENTIFIC_NAME) | SAMPLE_NAME (TAXON_ID) |
| attributes | Attributes (attribute_name/value/unit) | SAMPLE_ATTRIBUTES (TAG/VALUE/UNITS) | SAMPLE_ATTRIBUTES |
| package | Models | - | - |
| donor_id | - | - | DONOR_ID |
| sample_group_type | - | - | SAMPLE_GROUP_TYPE |

#### Experiment

| v3 | SRA Experiment | JGA Experiment |
|----|---------------|----------------|
| library.strategy | LIBRARY_STRATEGY | SEQUENCING_LIBRARY_STRATEGY / ARRAY strategies |
| library.source | LIBRARY_SOURCE | 同左 |
| library.selection | LIBRARY_SELECTION | 同左 |
| library.layout | LIBRARY_LAYOUT (SINGLE/PAIRED) | 同左 |
| library.nominal_length | PAIRED@nominal_length | 同左 |
| library.construction_protocol | LIBRARY_CONSTRUCTION_PROTOCOL | 同左 |
| platform.type | PLATFORM (family) | SEQUENCING_PLATFORM |
| platform.instrument_model | INSTRUMENT_MODEL | 同左 |
| platform.array_name | - | ARRAY_PLATFORM.array_name |
| platform.array_provider | - | ARRAY_PLATFORM.array_provider |
| targeted_loci | TARGETED_LOCI | 同左 |

#### Organism

| v3 | BP | BS | SRA | JGA | Trad | ST.26 |
|----|----|----|-----|-----|------|-------|
| name | OrganismName | OrganismName | SCIENTIFIC_NAME | SCIENTIFIC_NAME | organism qualifier | organism テキスト |
| taxonomy_id | Organism@taxID | Organism@taxonomy_id | TAXON_ID | TAXON_ID | /db_xref="taxon:XXX" | なし（DB側付与） |

#### Date フィールドの対応

| v3 フィールド | 対応する各形式の名称 |
|-------------|-------------------|
| submission.hold_date | BP: Hold/@release_date、SRA: HOLD/@HoldUntilDate、Trad: hold_date |
| runs[].run_date | SRA: Run/@run_date、JGA: Data/@data_acquisition_date |
| analyses[].analysis_date | SRA: Analysis/@analysis_date、JGA: Analysis/@analysis_date |
| project.publications[].date | BP: Publication/@date |

#### Relations の対応

| v2 | v3 |
|---|---|
| `submission.db_xrefs[{db, id}]` | `relations[{type: "xref", target: {db, id}}]` |
| （存在しない） | `relations[{type: "reference", target: {url}, label}]` |
| （存在しない） | `relations[{type: "child_of", target: {db, id}}]` |
| `feature.sequence_id` | `feature.sequence_id`（変更なし） |

#### Submission の責務分解（v2 → v3）

| v2 フィールド | v3 の帰属先 | 理由 |
|-----------|------------|------|
| submitters | **submission** | 提出行為のメタデータ |
| hold_date | **submission** | 提出行為のメタデータ |
| comments | **submission** | 提出行為のメタデータ |
| references | **project.publications** | 研究プロジェクトの属性 |
| keywords | **project.keywords** | 研究プロジェクトの属性 |
| locus_tag_prefix | **project.locus_tag_prefix** | BP XSD ProjectDescr に定義 |
| division | **Entry レベル or validator 導出** | アーカイブ分類 |
| trad_submission_category | **provenance.submission_category** | 変換元の分類情報（Option E 原則） |
| seq_prefix | **sequences.seq_prefix** | 配列エントリの命名規則 |
| datatype | **provenance.submission_category に統合** | データ種別 |
| db_xrefs | **ルート直下の relations** | 外部参照 |

### Submission Set と段階的更新フロー

典型的な登録パターン（record-idm の relation graph より）:

| パターン | 割合 | 含まれる DB |
|----------|------|------------|
| BP only | 47.0% | BioProject のみ |
| BP + BS + SRA | 33.8% | BioProject + BioSample + SRA |
| BP + BS + SRA + Trad | 6.7% | 全部入り |
| BP + BS + Trad | 6.4% | BioProject + BioSample + Trad |
| BP + BS | 5.3% | BioProject + BioSample |

段階的更新の例:

```jsonc
// Step 1: project のみ
{"project": {"alias": "my-project-2024", "title": "..."}}

// Step 2: accession 追記
{"project": {"alias": "my-project-2024", "accession": "PRJDB12345", "title": "..."}}

// Step 3: sample 追記
{"project": {"accession": "PRJDB12345", "title": "..."},
 "samples": [{"alias": "sample-1", "title": "..."}]}
```

record 内参照の例:

```jsonc
{
  "relations": [
    {"type": "part_of", "source": {"type": "experiment", "alias": "exp-1"}, "target": {"db": "sample", "id": "sample-1"}},
    {"type": "part_of", "source": {"type": "run", "alias": "run-1"}, "target": {"db": "experiment", "id": "exp-1"}}
  ]
}
```

### BioSample EAV 調査結果

validation rule 実装時の参考データ。

| 指標 | 値 |
|------|-----|
| DDBJ の unique attribute_name 数 | 1,153（ジャンク含む、実質 400-700） |
| NCBI の harmonized attributes | 960 |
| packages 数 | 229 (NCBI) / 228 (DDBJ) |
| 全 packages 共通の core attributes | 8 (sample_name, organism, taxonomy_id, bioproject_id, collection_date, geo_loc_name, sample_title, description) |
| 1 package あたりの最大属性数 | 203 (MIGS.eu.built) |
| 1 package あたりの平均属性数 | ~88 |
| いずれかの package で mandatory な属性数 | 103 |
| 常に optional な属性数 | 765 |

既存の typed 化の試み:

| プロジェクト | 方式 | 説明 |
|-------------|------|------|
| GenSC MIxS | LinkML (YAML) | MIxS v6.1+ の公式仕様。1000+ slots |
| NMDC Schema | LinkML | `Biosample` class を定義。MIxS ベース |
| EBI BioSamples | JSON Schema | チェックリストごとの JSON Schema |
| DDBJ RDF/OWL | OWL ontology | package/attribute を OWL class/property で定義 |

## 調査結果（参考資料）

### 各形式のスキーマ構造

XSD 定義（[ddbj/pub](https://github.com/ddbj/pub)）とスパコン上の実データを調査した結果。

#### 形式横断の共通パターン

| パターン | 使われる場所 | 説明 |
|----------|-------------|------|
| ObjectType | BP, BS, SRA 全 6 types, JGA 全 10 types | alias, center_name, accession, IDENTIFIERS を共有する基底構造 |
| RefNameGroup | SRA/JGA のオブジェクト間参照 | refname / refcenter / accession |
| ATTRIBUTES | SRA, JGA の全 object | TAG/VALUE/UNITS による自由形式メタデータ |
| EAV | BioSample | attribute_name/value による柔軟な属性 |
| Controlled-access chain | JGA 固有 | Dataset → Policy → DAC |
| FILE | SRA Run, JGA Data/Analysis | filename/filetype/checksum_method/checksum |
| LINKS | 全形式 | URL_LINK と XREF_LINK の 2 種類 |

#### BioProject (XSD: Core.xsd, Submission.xsd)

```
Project
├── ProjectID (ArchiveID, SecondaryArchiveID, CenterID, LocalID)
├── ProjectDescr (Name, Title, Description, ExternalLink, Grant, Publication, Keyword, Relevance, LocusTagPrefix)
└── ProjectType (choice)
    ├── TopSingleOrganism (Organism)
    ├── TopAdmin (umbrella, subtype: eDisease/eMetagenome/...)
    └── ProjectTypeSubmission (Target, Method, Objectives)
```

#### BioSample (XSD: biosample.xsd v1.2.0)

```
BioSample
├── Ids (1+, namespace: BioSample/SRA/...)
├── Description (Title, Organism, Comment)
├── Owner (Name, Contacts)
├── Models (1+, package version)
├── Attributes (1+, attribute_name/value/unit)
├── Links (url/db_xref)
└── Relations (derived_from/part_of)
```

#### SRA/DRA (XSD: v1.6)

```
SUBMISSION (@alias, @center_name, CONTACTS, ACTIONS)
STUDY      (DESCRIPTOR: STUDY_TITLE, STUDY_TYPE, STUDY_ABSTRACT, RELATED_STUDIES)
SAMPLE     (SAMPLE_NAME: TAXON_ID/SCIENTIFIC_NAME, SAMPLE_ATTRIBUTES)
EXPERIMENT (STUDY_REF, DESIGN: SAMPLE_DESCRIPTOR + LIBRARY_DESCRIPTOR, PLATFORM)
RUN        (EXPERIMENT_REF, DATA_BLOCK: FILES)
ANALYSIS   (STUDY_REF, ANALYSIS_TYPE, TARGETS, DATA_BLOCK/FILES)
```

主要 controlled vocabulary: LIBRARY_STRATEGY (43+), LIBRARY_SOURCE (8), LIBRARY_SELECTION (30+), PLATFORM (17 families, 80+ models)

#### JGA (XSD: v1.2)

SRA を拡張した 10 object types。SRA との差分:

- STUDY: + STUDY_TYPES (multiple), GRANTS, PUBLICATIONS
- SAMPLE: + DONOR_ID, SAMPLE_GROUP_TYPE
- EXPERIMENT: + ARRAY_PLATFORM
- DATA (SRA Run 相当): + DATA_TYPE, 拡張 file types (CEL, NIfTI, ...)
- ANALYSIS: + MICROARRAY, METABOLOMICS, PROTEOMICS, ...
- DATASET, POLICY, DAC: JGA 固有（controlled-access chain）
- SUBMISSION: + @nbdc_number

#### Assembly

```
NCBI: FASTA + AGP + chromosome list (TSV) + structured metadata
ENA:  ENA.assembly.xsd (ASSEMBLY_LEVEL, GENOME_REPRESENTATION, TAXON, WGS_SET, CHROMOSOMES)
```

#### ST.26

詳細は [st26.md](../st26.md) 参照。WIPO Standard ST.26。配列データ部分は INSDC DTD のサブセット。

#### GEA (MAGE-TAB 形式)

IDF (Investigation Description) + SDRF (Sample and Data Relationship)。SRA の library 情報を Comment フィールドで参照。BioProject/BioSample への参照あり。

### データソースの所在

| リポジトリ | パス | 形式 | サイズ目安 |
|-----------|------|------|----------|
| BioProject | `/usr/local/resources/bioproject/ddbj_core_bioproject.xml` | XML | 33 MB (DDBJ), 3.6 GB (全極) |
| BioSample | `/usr/local/resources/biosample/ddbj_biosample_set.xml.gz` | XML (gzip) | 31 MB gz (DDBJ), 4.3 GB gz (全極) |
| DRA | `/usr/local/resources/dra/fastq/{DRA000}/{DRA000XXX}/*.xml` | XML | ~230 万 submissions |
| JGA | `/usr/local/shared_data/jga/metadata-history/metadata/` | XML + CSV | study: 37K lines |
| GEA | `/usr/local/resources/gea/experiment/E-GEAD-{N000}/` | IDF/SDRF | ~682 experiments |
| Trad | `/usr/local/resources/trad/{ddbj,wgs,tsa,...}/` | flat file | ~1.87 億 records |

### XSD 参照方式

| 参照元 | 参照先 | 方式 |
|--------|--------|------|
| SRA Study | BioProject | STUDY_LINKS > XREF_LINK (db="bioproject") |
| SRA Sample | BioSample | EXTERNAL_ID (namespace="BioSample") |
| SRA Experiment | Study | STUDY_REF (refname or accession) |
| SRA Experiment | Sample | SAMPLE_DESCRIPTOR (refname or accession) |
| SRA Run | Experiment | EXPERIMENT_REF (refname or accession) |
| JGA Dataset | Policy | POLICY_REF (required) |
| JGA Policy | DAC | DAC_REF (required) |

## 未解決の設計判断

### データモデル

- [x] GFF 固有情報の保持方法 — トップレベル `gff` 廃止。record レベルは `provenance.gff`、feature レベルは `Feature.source_tool` / `Feature.score` で保持
- [x] Links と Relations の統合 — `links` 廃止、全て `relations` に統合
- [x] Assembly の Chromosome 二重管理 — Chromosome モデル廃止、Entry で表現
- [x] submission_category — `provenance.submission_category` に格納（Option E 原則）
- [x] Feature / Qualifier の識別子 — `id` → `alias` に rename
- [ ] GFF -> INSDC feature table の変換ルール定義
- [ ] GEA (IDF/SDRF) の record 表現 — Experiment/Sample との対応で十分か
- [ ] BioSample package（~229 種）の validation rule 化の具体的手法
- [ ] set 内の record 間の参照をどう解決するか（RefNameGroup の 2 フェーズ）

### Validation

- [ ] forbidden フィールドに値が入っていた場合、error か warning か
- [ ] 公開後の record に対する validation は skip するか
- [ ] fix の安全性レベル分類（`--fix=safe` / `--fix=all`）
- [ ] 外部リソース依存の fix（taxonomy DB 等）の扱い
- [ ] fix の結果を diff として表示する機能（dry-run）

### 技術的制約

- [ ] JSON ファイルサイズの実用上限（大規模ゲノムで数 GB になりうるか）
- [ ] streaming parse の必要性（巨大 JSON）
- [ ] binary data（配列本体）を JSON に含めるか、外部ファイル参照か

### 外部連携

- [ ] ENA の JSON schema を参考にするか
- [ ] 3 極間でのデータ互換性をどこまで意識するか
- [ ] converter のリポジトリ構成（この repo / 別 repo）
- [ ] dr_tools との関係（統合 / 分離）

### スコープ

- [x] Trad のゲノム細分化（MAG, SAG, haplotype）→ `provenance.submission_category` で表現
- [ ] GEA, MetaboBank, JVar はスコープに含めるか

## 優先順位とロードマップ

### 実装の優先順位

**trad + st26 の DFAST 登録向け validation rule を最優先で進める。**

### Tier 1: 最優先（trad/st26 DFAST validation に必要）

| # | 論点 | 状態 | 次のアクション |
|---|------|------|---------------|
| T1-1 | v3 スキーマの Pydantic モデル定義 | 未着手 | 確定したデータモデルを実装 |
| T1-2 | trad 向け validation rule の定義 | 未着手 | DFAST の登録要件を調査し rule 一覧を作成 |
| T1-3 | st26 向け validation rule の定義 | 未着手 | st26.md の調査結果をもとに rule 一覧を作成 |
| T1-4 | Validation 機構の実装（Rule interface, check/fix） | 未着手 | eslint 風の Rule protocol を実装 |
| T1-5 | Submission モデル | **確定** | |
| T1-6 | Sequences & Entries モデル | **確定** | |
| T1-7 | Features モデル | **確定** | |
| T1-8 | Assembly モデル | **確定** | |

### Tier 2: 高優先（データモデルの骨格）— 全て確定

| # | 論点 | 状態 |
|---|------|------|
| T2-1 | Project モデル（Publication, Grant, ProjectTarget 含む） | **確定** |
| T2-2 | Sample モデル（Attribute 含む） | **確定** |
| T2-3 | accession / alias 設計 | **確定** |
| T2-4 | Links と Relations の型定義 | **確定** |
| T2-5 | Person / Organization の統一モデル | **確定** |
| T2-6 | Organism の統一モデル | **確定** |
| T2-7 | Date フィールドの型定義 | **確定** |

### Tier 3: 中優先（拡張形式）— ほぼ確定

| # | 論点 | 状態 |
|---|------|------|
| T3-1 | Experiment モデル（LibraryDescriptor, Platform 含む） | **確定** |
| T3-2 | Run モデル（File 含む） | **確定** |
| T3-3 | Analysis モデル | **確定** |
| T3-4 | Dataset モデル | **確定** |
| T3-5 | Access Control (Policy/DAC) | **確定** |
| T3-6 | GEA validation の設計 | 未着手 |
| T3-7 | EAV 方針 | **確定**（EAV 維持） |

### Tier 4: 低優先（converter, 周辺機能）

| # | 論点 | 状態 |
|---|------|------|
| T4-1 | GFF round-trip converter の設計 | 議論中 |
| T4-2 | IDF/SDRF converter の設計 | 未着手 |
| T4-3 | v2 → v3 migration converter | 未着手 |
| T4-4 | Converter のリポジトリ構成 | 未決定 |
| T4-5 | dr_tools との関係整理 | 未決定 |

### Tier 5: 将来課題

| # | 論点 | 状態 |
|---|------|------|
| T5-1 | キュレーター問い合わせ情報の KV フィールド | 保留 |
| T5-2 | record_status / submission_stage の扱い | 保留 |
| T5-3 | JSON ファイルサイズの実用上限 | 未調査 |
| T5-4 | ENA の JSON schema との整合性 | 未調査 |
| T5-5 | GEA, MetaboBank, JVar のスコープ判断 | 未決定 |
| T5-6 | fix の安全性レベル分類 | 保留 |
| T5-7 | JGA の承認ワークフローと status の関係 | 保留 |

## Converter 戦略

```
+----------+     +-----------+     +----------+
| Raw      | --> | DdbjRecord| --> | Submit   |
| formats  |     | v3 (JSON) |     | formats  |
+----------+     +-----------+     +----------+

Raw formats:        Submit formats:
- Trad annotation   - DDBJ flat file
- GFF               - BioProject XML
- ST.26 XML         - BioSample XML
- SRA XML           - SRA XML
- BioProject XML    - JGA XML
- BioSample XML     - Assembly submission
- JGA XML           - GFF (round-trip)
- IDF/SDRF (GEA)
```

## ENA との関係

- ENA は独自に JSON 化を進めており、ENA 仕様に寄っている可能性がある
- BioSample の `name` を ENA だけ `alias` という単語で運用していたことが判明し、`name` に直すよう合意済み
- ENA には BioProject ではなく `study` があり、そこに BioProject を link している

参考: <https://ena-docs.readthedocs.io/en/latest/submit/general-guide/programmatic.html>
