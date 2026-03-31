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

### Open questions

- [ ] Trad のゲノム細分化（MAG, SAG, haplotype）は `trad_submission_category` の拡張か、別の軸か
- [ ] GEA, MetaboBank, JVar はスコープに含めるか
- [ ] ENA の JSON 化動向をどこまで意識するか

## 調査結果: 各形式のスキーマ構造

XSD 定義（[ddbj/pub](https://github.com/ddbj/pub)）とスパコン上の実データを調査した結果。

### 形式横断の共通パターン

| パターン | 使われる場所 | 説明 |
|----------|-------------|------|
| ObjectType | BP, BS, SRA 全 6 types, JGA 全 10 types | alias, center_name, accession, IDENTIFIERS を共有する基底構造 |
| RefNameGroup | SRA/JGA のオブジェクト間参照 | refname（登録前のローカル名）/ refcenter / accession（登録後） |
| ATTRIBUTES | SRA, JGA の全 object | TAG/VALUE/UNITS による自由形式メタデータ |
| EAV | BioSample | attribute_name/value による柔軟な属性。~150 packages で必須/任意を制御 |
| Controlled-access chain | JGA 固有 | Dataset → Policy → DAC のアクセス制御チェーン |
| FILE | SRA Run, JGA Data/Analysis | filename/filetype/checksum_method/checksum によるファイル管理 |
| LINKS | 全形式 | URL_LINK と XREF_LINK（DB cross-reference）の 2 種類 |

### BioProject (XSD: Core.xsd, Submission.xsd)

スキーマ: [ddbj/pub/docs/bioproject/xsd/](https://github.com/ddbj/pub/tree/master/docs/bioproject/xsd/)

```
Project
├── ProjectID
│   ├── ArchiveID (accession: PRJNA/PRJDB/PRJEB, archive: NCBI/DDBJ/EBI)
│   ├── SecondaryArchiveID (0+, replaced accessions)
│   ├── CenterID (0+)
│   └── LocalID (0+)
├── ProjectDescr
│   ├── Name (optional)
│   ├── Title (required)
│   ├── Description (optional)
│   ├── ExternalLink (0+, URL or dbXREF)
│   ├── Grant (0+, Title/Agency/GrantId)
│   ├── Publication (0+, Reference/StructuredCitation/DbType)
│   ├── ProjectReleaseDate (optional)
│   ├── Keyword (0+)
│   ├── Relevance (optional: Agricultural/Medical/Industrial/Environmental/Evolution/ModelOrganism)
│   ├── LocusTagPrefix (0+, biosample_id/assembly_id attributes)
│   └── UserTerm (0+, key-value with term/category/units)
└── ProjectType (choice)
    ├── ProjectTypeTopSingleOrganism (single species)
    │   └── Organism (required: taxID, species, OrganismName, Strain, BiologicalProperties)
    ├── ProjectTypeTopAdmin (umbrella/multi-disciplinary)
    │   └── subtype: eDisease/eMetagenome/eFundingInitiative/eOther/...
    └── ProjectTypeSubmission (submitter-level)
        ├── Target (sample_scope/material/capture, Organism, BioSampleSet)
        ├── Method (eSequencing/eArray/eMassSpectrometry/eOther)
        └── Objectives (data_type: eRawSequenceReads/eAssembly/eAnnotation/eVariation/...)
```

- sample_scope: eMonoisolate, eMultispecies, eEnvironment, eSynthetic, eSingleCell, ...
- material: eGenome, eTranscriptome, eProteome, ePhenotype, ...
- capture: eWhole, eExome, eTargetedLocusLoci, ...

Submission は Organization（type/role/Contact）+ Hold（release_date）+ Access（public/controlled-access）+ Action（ADD/MODIFY/SUPPRESS/HOLD/RELEASE）で構成。

### BioSample (XSD: biosample.xsd v1.2.0)

スキーマ: [ddbj/pub/docs/biosample/xsd/](https://github.com/ddbj/pub/tree/master/docs/biosample/xsd/)

```
BioSample (@access: public/controlled-access, @last_update, @publication_date)
├── Ids (required, 1+)
│   └── Id (@namespace: BioSample/SRA/dbGaP/GEO/Coriell/ATCC/..., @is_primary)
├── Description (required)
│   ├── SampleName (optional)
│   ├── Synonym (0+)
│   ├── Title (required)
│   ├── Organism (required, 1+)
│   │   ├── OrganismName (required)
│   │   ├── Strain/IsolateName/Breed/Cultivar/Label (all optional)
│   │   └── @taxonomy_id
│   └── Comment (optional)
├── Owner (required)
│   └── Name (+abbreviation, +url), Contacts
├── Models (required, 1+)
│   └── Model (text + @version)
├── Attributes (required, 1+)
│   └── Attribute (@attribute_name: required, @unit: optional, value: text or Id ref)
├── Links (optional)
│   └── Link (@type: url/db_xref, @target, @label)
└── Relations (optional)
    └── Relation (@type: derived_from/part_of, To: accession)
```

- EAV パターン: attribute_name でキーを指定し、テキスト値を格納
- ~150 packages（MIGS.ba, Pathogen.cl.1.0, Human.1.0 等）が mandatory/optional を定義
- Relations で BioSample 間の derived_from / part_of を表現

### SRA/DRA (XSD: v1.6)

スキーマ: [ddbj/pub/docs/dra/xsd/1-6/](https://github.com/ddbj/pub/tree/master/docs/dra/xsd/1-6/)

6 object types の構造:

```
SUBMISSION (@alias, @center_name, @accession, @submission_date)
├── CONTACTS (0+)
└── ACTIONS (ADD/MODIFY/SUPPRESS/HOLD/RELEASE/VALIDATE)

STUDY (@alias, @center_name, @accession)
├── DESCRIPTOR
│   ├── STUDY_TITLE (required)
│   ├── STUDY_TYPE (@existing_study_type: WGS/Metagenomics/Transcriptome/Epigenetics/...)
│   ├── STUDY_ABSTRACT (optional)
│   └── RELATED_STUDIES (optional)
├── STUDY_LINKS, STUDY_ATTRIBUTES

SAMPLE (@alias, @center_name, @accession)
├── SAMPLE_NAME
│   ├── TAXON_ID (required)
│   ├── SCIENTIFIC_NAME, COMMON_NAME (optional)
│   └── ANONYMIZED_NAME, INDIVIDUAL_NAME (optional)
├── SAMPLE_LINKS, SAMPLE_ATTRIBUTES

EXPERIMENT (@alias, @center_name, @accession)
├── STUDY_REF (required, -> Study)
├── DESIGN
│   ├── SAMPLE_DESCRIPTOR (-> Sample, optional POOL for multiplexing)
│   └── LIBRARY_DESCRIPTOR
│       ├── LIBRARY_NAME (optional)
│       ├── LIBRARY_STRATEGY (required, 43+ values)
│       ├── LIBRARY_SOURCE (required, 8 values)
│       ├── LIBRARY_SELECTION (required, 30+ values)
│       ├── LIBRARY_LAYOUT (SINGLE or PAIRED with nominal_length/sdev)
│       ├── TARGETED_LOCI (optional, 16S rRNA/18S rRNA/exome/...)
│       └── LIBRARY_CONSTRUCTION_PROTOCOL (optional)
├── PLATFORM (required, 17 families, 80+ instrument models)
├── EXPERIMENT_LINKS, EXPERIMENT_ATTRIBUTES

RUN (@alias, @accession, @run_date, @run_center)
├── EXPERIMENT_REF (required, -> Experiment)
└── DATA_BLOCK
    └── FILES (1+)
        └── FILE (@filename, @filetype: fastq/bam/cram/..., @checksum_method: MD5, @checksum)

ANALYSIS (@alias, @accession, @analysis_date)
├── STUDY_REF (required, -> Study)
├── ANALYSIS_TYPE (choice)
│   ├── DE_NOVO_ASSEMBLY
│   ├── REFERENCE_ALIGNMENT (+ Assembly + RUN_LABELS + SEQ_LABELS)
│   ├── SEQUENCE_ANNOTATION
│   └── ABUNDANCE_MEASUREMENT
├── TARGETS (0+, -> RUN/SAMPLE/EXPERIMENT/STUDY)
└── DATA_BLOCK/FILES (output files: bam/vcf/gff/bed/...)
```

主要な controlled vocabulary:

- LIBRARY_STRATEGY: WGS, WGA, WXS, RNA-Seq, ChIP-Seq, ATAC-seq, Hi-C, Bisulfite-Seq, AMPLICON, ...
- LIBRARY_SOURCE: GENOMIC, TRANSCRIPTOMIC, METAGENOMIC, GENOMIC SINGLE CELL, ...
- LIBRARY_SELECTION: RANDOM, PCR, cDNA, PolyA, ChIP, Hybrid Selection, ...
- PLATFORM: ILLUMINA, PACBIO_SMRT, OXFORD_NANOPORE, ION_TORRENT, BGISEQ, DNBSEQ, ELEMENT, ULTIMA, ...

### JGA (XSD: v1.2)

スキーマ: [ddbj/pub/docs/jga/xsd/1-2/](https://github.com/ddbj/pub/tree/master/docs/jga/xsd/1-2/)

SRA を拡張した 10 object types。SRA との差分を中心に記載:

```
STUDY - SRA Study + STUDY_TYPES (multiple allowed), GRANTS, PUBLICATIONS
  Study types: Case-Control, Cohort, Family, Twin, Clinical Trial, GWAS, ...

SAMPLE - SRA Sample + DONOR_ID, SAMPLE_GROUP_TYPE (case/control/cancer)

EXPERIMENT - SRA Experiment + ARRAY_PLATFORM (array strategies)
  + Genotyping by array, Transcription profiling by array, ...

DATA (SRA Run equivalent)
  + DATA_TYPE: SEQUENCING, REFERENCE_ALIGNMENT, ARRAY_HYBRIDIZATION, METABOLITE_ASSAY, IMAGE
  + Extended file types: CEL, NIfTI, Analyze, ...

ANALYSIS - SRA Analysis + extended types
  + MICROARRAY, METABOLOMICS, PROTEOMICS, BIOCHEMICAL_ASSAY, IMAGE, DOCUMENT

DATASET (JGA-specific, controlled-access)
  ├── TITLE (required)
  ├── DATASET_TYPE (0+, e.g. "Exome sequencing", "Genotyping by array")
  ├── DATA_REFS (-> Data), ANALYSIS_REFS (-> Analysis)
  └── POLICY_REF (required, -> Policy)

POLICY (JGA-specific)
  ├── TITLE (required)
  ├── DAC_REF (required, -> DAC)
  └── POLICY_TEXT or POLICY_FILE

DAC (JGA-specific, Data Access Committee)
  └── CONTACTS (required, 1+: name, email, organisation)

SUBMISSION - SRA Submission + @nbdc_number (required, NBDC approval)
  + PROTECT action (EGA integration)
```

JGA 申請管理システム（jga-shinsei）のステータス:

| Code | 意味 | record-idm mapping |
|------|------|--------------------|
| 10 | 申請書類作成中 | draft |
| 20 | 申請完了 | submitted |
| 30 | 差し戻し中 | revision_requested |
| 40 | 審査中 | in_curation |
| 50 | 申請却下 | rejected (canceled) |
| 60 | 申請承認 | accepted |
| 70 | 申請取り下げ | canceled |
| 80 | 利用期間終了 | (closed) |

### GEA (MAGE-TAB 形式)

XML スキーマなし。IDF/SDRF テキスト形式。

```
IDF (Investigation Description Format):
  Investigation Title, Experiment Description
  Experimental Design, Experimental Factor Name/Type
  Person (Last Name, First Name, Affiliation, Roles)
  Public Release Date, PubMed ID
  Protocol (Name, Type, Description)
  Comment[BioProject], Comment[GEAAccession]

SDRF (Sample and Data Relationship Format):
  Source Name, Characteristics[organism/taxonomy_id/strain/...]
  Comment[BioSample], Comment[sample_title]
  Comment[LIBRARY_LAYOUT/SELECTION/SOURCE/STRATEGY/INSTRUMENT_MODEL]
  Comment[SRA_EXPERIMENT], Comment[SRA_RUN]
  Array Data File, Derived Array Data Matrix File
```

- SRA の library 情報を Comment フィールドで参照
- BioProject, BioSample への参照あり

### Assembly

XML ベースのスキーマは ENA のみ（ENA.assembly.xsd）。NCBI は AGP + TSV。

```
NCBI Assembly submission:
  ├── FASTA files (.fsa)
  ├── AGP file (9-column TSV: scaffold/chromosome assembly from contigs)
  ├── Chromosome list (TSV: OBJECT_NAME, CHROMOSOME_NAME, TYPE, TOPOLOGY)
  └── Structured metadata (web form or Genome Info TSV)

ENA Assembly XML (ENA.assembly.xsd):
  ├── TITLE, NAME
  ├── ASSEMBLY_LEVEL (complete genome/chromosome/scaffold/contig)
  ├── GENOME_REPRESENTATION (full/partial)
  ├── TAXON (TAXON_ID, SCIENTIFIC_NAME, STRAIN)
  ├── STUDY_REF, SAMPLE_REF
  ├── WGS_SET (PREFIX, VERSION)
  └── CHROMOSOMES (NAME, TYPE: Chromosome/Mitochondrion/Plasmid/Chloroplast/...)
```

- assembly_summary_genbank.txt はスパコン上の trad/ には存在しない（NCBI FTP から取得）
- AGP v2.1: component_type (A/D/F/G/O/P/W = sequence, N/U = gap)、gap_type (scaffold/contig/centromere/telomere/...)

### ST.26 (調査済み)

詳細は [st26.md](../st26.md) を参照。WIPO Standard ST.26 は特許配列リストを XML で記述する国際標準。配列データ部分は INSDC DTD のサブセット。INSDSeq_division は "PAT" 固定。

### データソースの所在

スパコン上のパスと形式:

| リポジトリ | パス | 形式 | サイズ目安 |
|-----------|------|------|----------|
| BioProject | `/usr/local/resources/bioproject/ddbj_core_bioproject.xml` | XML (PackageSet) | 33 MB (DDBJ), 3.6 GB (全極) |
| BioSample | `/usr/local/resources/biosample/ddbj_biosample_set.xml.gz` | XML (gzip) | 31 MB gz (DDBJ), 4.3 GB gz (全極) |
| DRA | `/usr/local/resources/dra/fastq/{DRA000}/{DRA000XXX}/*.xml` | XML (5 types per submission) | ~230 万 submissions |
| JGA | `/usr/local/shared_data/jga/metadata-history/metadata/` | XML (7 types) + CSV (relations, dates) | study: 37K lines, dataset: 442K lines |
| GEA | `/usr/local/resources/gea/experiment/E-GEAD-{N000}/` | IDF/SDRF (TSV) | ~682 experiments |
| Trad | `/usr/local/resources/trad/{ddbj,wgs,tsa,...}/` | flat file (.seq.gz) | ~1.87 億 records |
| SRA Accessions | `/lustre9/open/database/ddbj-dbt/dra-private/mirror/SRA_Accessions/` | TSV (20 columns) | ~30 GB |
| Assembly summary | NCBI FTP (streaming) | TSV | - |

## データモデル設計

### Top-level 構造

v2 の DdbjRecord:

```
DdbjRecord
├── schema_version: str
├── provenance: Provenance
├── submission: Submission
├── experiments: list[Experiment]
├── sequences: Sequences
│   ├── common_source: Source
│   └── entries: list[Entry]
└── features: list[Feature]
```

v3 では、Trad 以外の形式（BP, BS, SRA, JGA 等）も表現する必要がある。調査の結果、各形式は独立したオブジェクト構造を持つが、概念レベルでの共通化が可能と判明した。

#### 議論ログ: 概念の統合

DB ごとのサイロ化ではなく、ontology に基づいてフィールドを統合する方針を決定:

| v3 の統一概念 | 統合元 |
|-------------|-------|
| **Project** | BioProject + SRA Study + JGA Study |
| **Sample** | BioSample + SRA Sample + JGA Sample |
| **Experiment** | SRA Experiment + JGA Experiment |
| **Run/Data** | SRA Run + JGA Data |
| **Analysis** | SRA Analysis + JGA Analysis |
| **Sequences** | Trad entries + ST.26 sequences (そのまま) |
| **Features** | INSDC feature table (そのまま) |
| **Assembly** | Assembly 情報 (新規) |
| **Access Control** | JGA Dataset + Policy + DAC (そのまま) |

共通化による複雑性は validator / converter で吸収する（例: BP → record → BP round-trip で正しさを検証）。

v3 の Top-level 構造案:

```
DdbjRecord (all fields Optional/None)
├── schema_version: str
├── provenance: Provenance | None       # data の来歴記録（変換元形式、ツールバージョン等）
├── submission: Submission | None       # thin: submitters, hold_date, comments only
├── links: list[Link] | None            # 外部リンク (URL) + DB 相互参照 (db_xref)
├── relations: list[Relation] | None    # 意味的関係 (child_of, derived_from, part_of, ...)
├── project: Project | None             # = BP + SRA Study + JGA Study
│   ├── title, description, organism
│   ├── publications                    # <- v2 submission.references
│   ├── keywords                        # <- v2 submission.keywords
│   ├── grants
│   ├── locus_tag_prefix                # <- v2 submission, BP XSD ProjectDescr
│   └── division                        # <- v2 submission (or auto-derived)
├── samples: list[Sample] | None        # = BS + SRA Sample + JGA Sample
├── experiments: list[Experiment] | None # SRA/JGA experiment (library, platform)
├── runs: list[Run] | None              # SRA Run + JGA Data (files)
│   └── run_date                        # submitter 指定の data 取得日
├── analyses: list[Analysis] | None     # SRA/JGA analysis (analysis_type, files)
│   └── analysis_date                   # submitter 指定の解析実施日
├── sequences: Sequences | None         # Trad/ST.26 (entries, common_source)
│   └── seq_prefix                      # <- v2 submission
├── features: list[Feature] | None      # INSDC feature table
├── assembly: Assembly | None           # assembly level, AGP, chromosomes
│   └── submission_category             # <- v2 submission.trad_submission_category
└── access_control: AccessControl | None # JGA Dataset/Policy/DAC
```

#### 議論ログ: DdbjRecord の粒度と形式識別

検討した 3 案:

| 案 | 1 JSON の単位 | 例 |
|---|---|---|
| A: 1 object | DB のオブジェクト 1 つ | bioproject.json, experiment.json, ... |
| B: 1 DB submission | 1 DB への提出単位 | sra_submission.json (study+experiment+run+sample を含む) |
| C: 1 submission set | 複数 DB にまたがる登録全体 | submission.json (BP+BS+SRA+Trad を全部含む) |

**決定: 案 E の徹底により A/B/C の区分を溶かす**

案 E（flat + validation rules）を徹底すると、DdbjRecord に record_type のような判別フィールドは不要になる:

- 全フィールドを flat に `T | None` で定義する
- validation rules が「何として有効か」を判定する
- record_type は validation rules の通過結果から **導出** される

具体例:

- `project` だけ埋める → BP validation rules が通る → BP として投稿可能
- `project` + `samples` を埋める → BP rules も BS rules も通る → BP+BS として投稿可能
- 後から `experiments` + `runs` を追記 → SRA validation rules も通るようになる

この方式の利点:

- record_type を宣言する必要がない（validation 結果から導出）
- 1 つの DdbjRecord に複数 DB の情報を段階的に追加できる
- API 側は「どの validation rules が通ったか」を見て適切な DB に投入する
- A/B/C すべてのユースケースを 1 つの仕組みで包含する

#### 議論ログ: Tier 1 構造的決定

| # | 論点 | 決定 |
|---|------|------|
| 1 | provenance | 維持。data の来歴記録用（変換元形式、ツールバージョン等）。record から直接書き始めるケースも考慮し、provenance がない record も有効とする。record の metadata の metadata という位置付け |
| 2 | ObjectType 基底モデル | 作らない。accession, alias 等は各概念（project, sample 等）が個別に持つ |
| 3 | submitter 統一 | Person + Organization の統一モデルを定義。各形式の差異は validation rule で吸収 |
| 5 | hold_date | 要調査: 全形式の date フィールドを洗い出してから判断 |
| 6 | organism 共有 | 共通の Organism 型を定義し再利用。taxonomy dump の追加調査が必要 |
| 7 | EAV | EAV を完全にやめたい。要検討 |
| 8 | status | record に含めない。status は record-idm の責務であり外部メタデータ。record は純粋な data を表す。理由: (1) 同じ data が status 変化しても data 自体は変わらない (2) status は DB 側の管理情報 (3) validation config と同様に外付けすべき |
| 9 | id / 参照 | 保留 |

未決定で議論が必要:

- #4: db_xrefs / links — 単純な cross-ref だけでなく親子関係（umbrella 等）も表現する必要がある
- #7: EAV 廃止 — BioSample の ~150 packages をどう扱うか

#### Open questions

- [x] ~~1 つの DdbjRecord が 1 つの形式を表すか~~ → 案 E により区分不要
- [x] ~~形式識別子のフィールド名~~ → 不要。validation rules から導出
- [x] ~~provenance を維持するか~~ → 維持。来歴記録用
- [x] ~~ObjectType 基底モデル~~ → 作らない
- [x] ~~status を record に含めるか~~ → 含めない（外部メタデータ）
- [ ] sequences / features / experiments は Trad 固有の概念。他形式ではどうなるか
- [ ] フィールド数が膨大になる可能性。全形式のフィールドを 1 モデルに flat に並べた場合の実用性
- [x] ~~db_xrefs / links の設計~~ → links（外部参照）と relations（意味的関係）を分離。ルート直下に配置
- [ ] EAV を完全にやめる方法の検討 — 調査完了、方針検討中（「EAV 廃止の調査結果と方針」参照）

### Submission モデル

#### 議論ログ: submission の責務分解

v2 の Submission は「features と sequences 以外の全部」を押し込んだ結果、責務が混在していた。べき論に基づいて分解する:

| フィールド | v2 の場所 | v3 の帰属先 | 理由 |
|-----------|----------|------------|------|
| submitters | submission | **submission** | 提出行為のメタデータ |
| hold_date | submission | **submission** | 提出行為のメタデータ |
| comments | submission | **submission** | 提出行為のメタデータ |
| references | submission | **project** | BP の Publication に相当。研究プロジェクトの属性 |
| keywords | submission | **project** | BP の Keyword に相当。研究プロジェクトの属性 |
| locus_tag_prefix | submission | **project** | BP XSD の ProjectDescr に定義。プロジェクトの属性 |
| division | submission | **project** or 導出 | organism + sample + 文脈から決まるアーカイブ分類 |
| trad_submission_category | submission | **assembly** | アセンブリの種別・完成度（WGS/GNM/MAG/SAG/haplotype） |
| seq_prefix | submission | **sequences** | 配列エントリの命名規則 |
| datatype | submission | **project** or **assembly** | データ種別の分類 |
| db_xrefs | submission | **ルート直下に links + relations として分離** | 下記「Links と Relations の設計」参照 |

**決定: submission は提出行為のメタデータに限定する（thin submission）**

```
Submission (thin)
├── submitters: list[Person] | None
├── hold_date: str | None
└── comments: list[str] | None
```

各形式での submitter / contact 情報の表現:

| 形式 | 提出者の表現 | 備考 |
|------|-------------|------|
| Trad (v2) | Person (name, abbreviation, email, orcid, Organization) | submitters[0] が contact |
| BioProject XSD | Organization (Name, Contact: email/phone/Address) | role: owner/participant |
| BioSample XSD | Owner > Name + Contacts (email, lab, department) | Organization 単位 |
| SRA XSD | SUBMISSION > CONTACTS (name, inform_on_status/error) | 通知先としての contact |
| JGA XSD | DAC > CONTACTS (name, email, organisation) | DAC の委員 |
| JGA 申請 | PI (last_name, first_name, institution) + Submitter + Head | 3 種の担当者 |

#### Open questions

- [x] ~~submitter 情報は全形式で共通化できるか~~ → Person + Organization の統一モデルで共通化。形式差異は validation rule で吸収
- [x] ~~db_xrefs / links の設計~~ → 下記「Links と Relations の設計」で解決。links（外部参照）と relations（意味的関係）を分離
- [x] ~~hold_date / date 周りの統一~~ → 下記「Date フィールドの設計」で解決

### Sequences & Entries

Trad / ST.26 固有のモデル。v3 でも塩基配列登録で使用。

v2 からの変更: `seq_prefix` を submission から移動。

```
Sequences
├── seq_prefix: str | None              # <- v2 submission.seq_prefix
├── common_source: Source | None
└── entries: list[Entry] | None
```

#### Open questions

- [ ] 大規模ゲノム（数万エントリ）での JSON サイズ実用性
- [ ] common_source の organism と project.organism / sample.organism の関係
  - 概念的に同じ。統合するか、それぞれが持つか

### Features

INSDC feature table に基づくアノテーション。現行の INSDC validation（YAML rule）を継続。

#### Open questions

- [ ] ST.26 は INSDC のサブセット。validation rule の差異をどう表現するか
- [ ] GFF 由来の feature との対応付け
- [ ] location 構文の validation（未実装、Biopython 連携？）

### Project (= BioProject + SRA Study + JGA Study の統合)

v2 には存在しないモデル。v3 で新規追加。DB 横断で「研究プロジェクト」を統一的に表現する。

統合元の主要フィールド:

| フィールド | BioProject | SRA Study | JGA Study |
|-----------|-----------|-----------|-----------|
| title | Title (required) | STUDY_TITLE (required) | STUDY_TITLE (required) |
| description | Description | STUDY_ABSTRACT | STUDY_ABSTRACT |
| project_type | TopSingleOrganism / TopAdmin / Submission | STUDY_TYPE (WGS/Metagenomics/...) | STUDY_TYPES (multiple: Case-Control/Cohort/...) |
| organism | Organism (taxID, strain, BiologicalProperties) | - (Sample 側) | - (Sample 側) |
| grants | Grant (Agency, GrantId) | - | GRANTS |
| publications | Publication (PMID, DOI) | STUDY_LINKS | PUBLICATIONS |
| keywords | Keyword (0+) | - | - |
| relevance | Agricultural/Medical/Industrial/... | - | - |
| locus_tag_prefix | LocusTagPrefix | - | - |
| target | sample_scope, material, capture | - | - |
| related_projects | Links.xsd Hierarchical (umbrella) | RELATED_STUDIES | - |

#### Open questions

- [ ] Project の必須フィールド — title のみか、organism も含めるか
- [ ] project_type の統合 — BP の 3 種と SRA/JGA の study_type をどうマージするか
  - BP TopAdmin (umbrella) は特殊。project_type の 1 値として扱うか
- [ ] Umbrella BioProject の扱い
  - 複数 Project の登録を 1 JSON で許容するか
  - 親子関係の表現方法
  - 調査結果: 144 umbrella、99.6% が depth 1（umbrella → leaf のみ）
- [ ] BP 固有の target (sample_scope/material/capture) をどこに置くか
- [ ] SRA study の RELATED_STUDIES と BP の Links.xsd Hierarchical を統合するか

### Sample (= BioSample + SRA Sample + JGA Sample の統合)

v2 には存在しないモデル。v3 で新規追加。DB 横断で「試料」を統一的に表現する。

統合元の主要フィールド:

| フィールド | BioSample | SRA Sample | JGA Sample |
|-----------|-----------|-----------|-----------|
| title | Title (required) | TITLE | TITLE |
| organism | Organism (taxonomy_id, strain, breed, cultivar) | SAMPLE_NAME (TAXON_ID, SCIENTIFIC_NAME) | SAMPLE_NAME (TAXON_ID) |
| attributes | Attributes (EAV: attribute_name/value/unit) | SAMPLE_ATTRIBUTES (TAG/VALUE/UNITS) | SAMPLE_ATTRIBUTES |
| models/packages | Models (MIGS.ba, Pathogen.cl.1.0, ...) | - | - |
| relations | Relations (derived_from/part_of) | - | - |
| anonymized_name | - | ANONYMIZED_NAME | ANONYMIZED_NAME |
| donor_id | - | - | DONOR_ID |
| sample_group_type | - | - | SAMPLE_GROUP_TYPE (case/control/cancer) |

注目点: BioSample の EAV と SRA/JGA の SAMPLE_ATTRIBUTES は同じパターン（TAG/VALUE）。統一可能。

#### Open questions

- [ ] EAV を完全にやめる方法の検討（下記「EAV 廃止の調査結果と方針」参照）
- [ ] BioSample package（~229 種）の validation rule 化
  - INSDC feature table と同じ YAML パターンで定義可能
  - 機械可読な定義が既に存在: NCBI XML, DDBJ xlsx, DDBJ RDF/OWL, GenSC MIxS LinkML
- [ ] BioSample Relations（derived_from/part_of）を v3 でどう表現するか
  - Sample 間の関係グラフ。record-idm の relation とは別概念
- [ ] Trad の common_source（organism + mol_type + qualifiers）との関係
  - Sample の organism と common_source の organism は概念的に同じ。統合するか

### Experiment (SRA + JGA 共通)

v2 には限定的に存在（ST_COMMENT 用）。v3 では SRA/JGA の実験メタデータを統一的に表現する。

study → Project に統合済み、sample → Sample に統合済みのため、Experiment 以下が SRA/JGA 固有の概念として残る。

統合元の主要フィールド:

| フィールド | SRA Experiment | JGA Experiment |
|-----------|---------------|----------------|
| library_strategy | LIBRARY_STRATEGY (43+ enum) | SEQUENCING_LIBRARY_STRATEGY + ARRAY strategies |
| library_source | LIBRARY_SOURCE (8 enum) | 同左 |
| library_selection | LIBRARY_SELECTION (30+ enum) | 同左 |
| library_layout | SINGLE / PAIRED (nominal_length, sdev) | 同左 (optional) |
| platform | PLATFORM (17 families, 80+ models) | SEQUENCING_PLATFORM + ARRAY_PLATFORM |
| targeted_loci | TARGETED_LOCI (16S rRNA, exome, ...) | 同左 |
| protocol | LIBRARY_CONSTRUCTION_PROTOCOL | 同左 |

JGA の拡張: ARRAY_PLATFORM（array_name, array_description, array_provider）

#### Open questions

- [ ] Experiment の controlled vocabulary（strategy/source/selection/platform）の管理方法
  - YAML 外部定義? Pydantic Literal? 両方?
  - XSD の enum は頻繁に更新される（新しい sequencer 追加等）
- [ ] JGA の array platform をどう統合するか — platform の拡張として扱うか、別フィールドか

### Run / Data (SRA Run + JGA Data の統合)

データファイルの管理。

| フィールド | SRA Run | JGA Data |
|-----------|---------|----------|
| files | FILES (filename, filetype, checksum) | FILES (同構造) |
| data_type | - | DATA_TYPE (sequencing/array/metabolite/image) |
| file types | 31 enum (fastq, bam, cram, ...) | 65+ enum (+ CEL, NIfTI, Analyze, ...) |

#### Open questions

- [ ] 名称: "run" か "data" か — JGA では "Data" と呼ぶ
- [ ] JGA の拡張 file types (CEL, NIfTI 等) を同じ enum に含めるか、validation rule で分けるか

### Analysis (SRA + JGA 共通)

二次解析結果。

| フィールド | SRA Analysis | JGA Analysis |
|-----------|-------------|--------------|
| analysis_type | 4 types (DE_NOVO_ASSEMBLY, REFERENCE_ALIGNMENT, SEQUENCE_ANNOTATION, ABUNDANCE_MEASUREMENT) | 4 + MICROARRAY, METABOLOMICS, PROTEOMICS, BIOCHEMICAL_ASSAY, IMAGE, DOCUMENT |
| files | AnalysisFileType (bam, vcf, gff, ...) | 拡張 (+ metabolomics, proteomics formats) |
| references | STUDY_REF, TARGETS (-> run/sample/experiment) | STUDY_REFS, SAMPLE_REFS, DATA_REFS |

#### Open questions

- [ ] SRA の 4 types と JGA の 11+ types を 1 つの enum にするか
  - 案 E: 全値を 1 enum に入れ、validation rule で「SRA submission なら 4 types のみ許可」
- [x] ~~study / sample は Project / Sample に統合~~ → 統合済み

### Access Control (JGA 固有)

JGA の controlled-access chain。Experiment, Run/Data, Analysis は SRA と統合済みのため、JGA 固有として残るのは Dataset → Policy → DAC のアクセス制御構造。

```
Dataset (Data + Analysis grouping)
├── dataset_type (0+)
├── data_refs (-> Run/Data)
├── analysis_refs (-> Analysis)
└── policy_ref (-> Policy, required)

Policy
├── dac_ref (-> DAC, required)
└── policy_text or policy_file

DAC (Data Access Committee)
└── contacts (name, email, organisation: required)
```

JGA Submission 固有: `nbdc_number`（NBDC 承認番号、required）

#### Open questions

- [ ] Dataset / Policy / DAC は DdbjRecord に含めるか、別管理か
  - DAC は組織情報であり、複数 Dataset で共有される
  - Policy も同様に再利用される可能性がある
- [ ] JGA の承認ワークフロー（却下あり）と status の関係
  - 10(作成中) → 20(申請完了) → 40(審査中) → 60(承認) / 50(却下)
  - record-idm の submission_stage に mapping 可能（rejected は JGA 固有）
- [ ] nbdc_number は submission レベルの共通フィールドに置くか、JGA 固有として validation rule で制約するか

### Assembly

現 v2 では ST_COMMENT として Experiment に埋め込まれている。v3 では独立モデルにする。

v2 からの変更: `trad_submission_category` を submission から移動し、`submission_category` として配置。

```
Assembly
├── submission_category: str | None     # <- v2 submission.trad_submission_category
│                                       #    WGS/GNM/MAG/SAG/haplotype
├── assembly_level: str | None          # complete genome/chromosome/scaffold/contig
├── genome_representation: str | None   # full/partial
├── assembly_accession: str | None      # GCA_/GCF_
├── chromosomes: list[Chromosome] | None
└── ...
```

調査結果:

- NCBI: XML スキーマなし。AGP ファイル + chromosome list (TSV) + structured metadata
- ENA: ENA.assembly.xsd あり（ASSEMBLY_LEVEL, GENOME_REPRESENTATION, TAXON, WGS_SET, CHROMOSOMES）
- BioProject XSD: Assembly.xsd あり（assemblyName, assemblyAccession, WGSprefix, LocusTagPrefix, Replicon list）
- スパコン: assembly_summary_genbank.txt は trad/ には未配置（NCBI FTP から streaming 取得）

#### Open questions

- [ ] submission_category の命名 — `trad_submission_category` を改名するか、そのままか
  - "trad" は Trad 固有の名前。v3 では assembly 一般の概念として使う
- [ ] NCBI Assembly 登録に必要な情報の整理
  - AGP file (9-column TSV: component/gap)
  - Chromosome list (TSV: object_name, chromosome_name, type, topology)
  - Assembly accession (GCA/GCF)
- [ ] Assembly index の生成機能はこの repo の責務か
- [ ] assembly_summary_genbank.txt との連携
- [ ] ENA の assembly XML を参考にするか（DDBJ/NCBI にはない形式）

### EAV 廃止の調査結果と方針

**方針: EAV を完全にやめたい。**

#### 調査結果

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
| 1 package にしか存在しない属性数 | 123 |
| unit の扱い | テキスト値に埋め込み（`"0.4 m"`）、構造化されていない |
| multi-value | なし（1 attribute = 1 value） |
| 機械可読な定義 | NCBI XML, DDBJ xlsx, DDBJ RDF/OWL, GenSC MIxS LinkML |

Top 20 attributes（DDBJ、844K samples 中の出現数）:

| 順位 | attribute | 出現数 |
|------|-----------|--------|
| 1 | sample_name | 844,129 |
| 2 | geo_loc_name | 731,576 |
| 3 | collection_date | 723,420 |
| 4 | lat_lon | 520,424 |
| 5 | bioproject_id | 440,806 |
| 6 | env_broad_scale | 419,995 |
| 7 | env_medium | 419,380 |
| 8 | env_local_scale | 419,315 |
| 9 | isolate | 315,277 |
| 10 | isolation_source | 271,960 |
| 11 | host | 267,184 |
| 12 | project_name | 215,806 |
| 13 | strain | 184,905 |
| 14 | tissue | 166,465 |
| 15 | age | 138,660 |
| 16 | metagenome_source | 134,714 |
| 17 | dev_stage | 118,511 |
| 18 | isol_growth_condt | 117,498 |
| 19 | derived_from | 117,171 |
| 20 | sex | 107,246 |

Top 20 packages（DDBJ）:

| 順位 | package | 件数 |
|------|---------|------|
| 1 | Generic | 115,750 |
| 2 | Plant | 66,630 |
| 3 | Metagenome.environmental | 63,458 |
| 4 | MIMAG | 60,806 |
| 5 | MIGS.eu | 56,436 |
| 6 | Model.organism.animal | 51,745 |
| 7 | MIMS.me.human-gut | 38,495 |
| 8 | MIMS.me.soil | 28,190 |
| 9 | Omics | 24,396 |
| 10 | Functional.genomics | 23,683 |

#### 既存の typed 化の試み

| プロジェクト | 方式 | 説明 |
|-------------|------|------|
| GenSC MIxS | LinkML (YAML) | MIxS v6.1+ の公式仕様。1000+ slots。JSON Schema, OWL 生成可能 |
| NMDC Schema | LinkML | `Biosample` class を定義。MIxS ベース |
| EBI BioSamples | JSON Schema | チェックリストごとの JSON Schema。MongoDB + biovalidator |
| DDBJ RDF/OWL | OWL ontology | package/attribute を OWL class/property で定義 |

#### Open questions

- [ ] 全 960 属性を typed fields にするか、よく使うものだけにするか
  - 全部: 案 E に完全一致。巨大だが一貫性がある
  - よく使うもの + catch-all: 実用的だが EAV が部分的に残る
- [ ] attribute の命名: NCBI の harmonized_name をそのまま使うか
- [ ] unit の扱い: テキスト埋め込みのまま（`"0.4 m"`）か、value + unit に分離するか
- [ ] package の validation rule 化の具体的手法
  - DDBJ xlsx / NCBI XML から自動生成する仕組みが必要

### Links と Relations の設計

#### 調査結果

全形式のリンク/関係パターンを調査し、4 カテゴリに分類:

| カテゴリ | 例 | XML での表現 |
|----------|-----|-------------|
| 外部リンク (URL) | Web ページ、カタログ | BP: `ExternalLink/URL`、SRA: `URL_LINK` |
| DB 相互参照 (db_xref) | PubMed, taxonomy, SRA accession | BP: `ExternalLink/dbXREF`、SRA: `XREF_LINK`、BS: `Link type="db_xref"` |
| 構造的/意味的関係 | umbrella 親子、derived_from、parasitic | BP: `Links.xsd Hierarchical/PeerProject`、BS: `Relations` |
| record 内参照 | experiment → sample | SRA: `EXPERIMENT_REF/SAMPLE_DESCRIPTOR (refname/accession)` |

#### 決定: links と relations を分離

BioSample XSD の設計を踏襲し、外部参照と意味的関係を分離する:

```
# links: 外部リソースへの参照（旧 submission.db_xrefs を昇格）
links: list[Link] | None
  Link = UrlLink | DbXrefLink  (discriminated by type)
  UrlLink:    {type: "url", url: str, label: str | None}
  DbXrefLink: {type: "db_xref", db: str, id: str, label: str | None}

# relations: レコード間の意味的・構造的関係
relations: list[Relation] | None
  Relation:
    type: "child_of" | "parent_of" | "derived_from" | "part_of" |
          "peer" | "same_as" | "replaced_by" | "replaces"
    target: {db: str, id: str}
    properties: dict[str, str] | None  # 追加属性（hierarchy_type 等）
```

v2 からの移行:

| v2 | v3 |
|---|---|
| `submission.db_xrefs[{db, id}]` | `links[{type: "db_xref", db, id}]` |
| （存在しない） | `links[{type: "url", url, label}]` |
| （存在しない） | `relations[{type, target}]` |
| `feature.sequence_id` | `feature.sequence_id`（変更なし） |

#### 設計の根拠

1. BioSample XSD が Links と Relations を明確に分離しており、意図が最も明確
2. links は「関連する外部リソースは何か」、relations は「他レコードとの意味的関係は何か」という異なる問い
3. relations の type enum で umbrella BP 親子（child_of）、BS 派生（derived_from/part_of）、Trad 置換（replaced_by）を統一的に表現

### Date フィールドの設計

#### 調査結果

全形式の date フィールドを横断調査し、submitter 指定と archive 管理に分類:

| カテゴリ | submitter 指定 | archive 管理 | v3 での扱い |
|----------|--------------|-------------|------------|
| hold/release | hold_date (BP/SRA/JGA/Trad) | - | **submission.hold_date** |
| created | - | create_date (BP/BS/DRA) | 外部メタデータ |
| submitted | - | submitted/submit_date (BP/SRA/JGA) | 外部メタデータ |
| modified | - | modified_date/last_update (全形式) | 外部メタデータ |
| published/released | - | release_date/publication_date/open_date | 外部メタデータ |
| distributed | - | dist_date (BP/BS/DRA/Trad) | 外部メタデータ |
| run/acquisition | run_date (SRA), data_acquisition_date (JGA) | - | **runs[].run_date** |
| analysis | analysis_date (SRA/JGA) | - | **analyses[].analysis_date** |
| sample collection | collection_date (BS attribute) | - | **samples[].collection_date** |
| sample preparation | preparation_date (BS) | - | **samples[].preparation_date** |
| publication (paper) | Publication/@date (BP/JGA) | - | **project.publications[].date** |

#### 決定: submitter 指定の date のみ record に含める

- **record は純粋な data** という原則に基づき、archive が管理する日付（created, modified, published 等）は record-idm の外部メタデータとして扱う
- submitter が指定する日付（hold_date, run_date, collection_date 等）は data の一部として record に含める

形式間の命名の不統一（publication_date vs release_date vs open_date 等）は v3 では統一する:

| v3 フィールド | 対応する各形式の名称 |
|-------------|-------------------|
| submission.hold_date | BP: Hold/@release_date、SRA: HOLD/@HoldUntilDate、Trad: hold_date |
| runs[].run_date | SRA: Run/@run_date、JGA: Data/@data_acquisition_date |
| analyses[].analysis_date | SRA: Analysis/@analysis_date、JGA: Analysis/@analysis_date |
| samples[].collection_date | BS: collection_date attribute |
| project.publications[].date | BP: Publication/@date |

## Submission Set の概念

1 つの「登録」が複数の DB にまたがるケースの扱い。

典型的な登録パターン（record-idm の relation graph より）:

| パターン | 割合 | 含まれる DB |
|----------|------|------------|
| BP only | 47.0% | BioProject のみ |
| BP + BS + SRA | 33.8% | BioProject + BioSample + SRA |
| BP + BS + SRA + Trad | 6.7% | 全部入り |
| BP + BS + Trad | 6.4% | BioProject + BioSample + Trad |
| BP + BS | 5.3% | BioProject + BioSample |

XSD 調査で判明した参照方式:

| 参照元 | 参照先 | 方式 |
|--------|--------|------|
| SRA Study | BioProject | STUDY_LINKS > XREF_LINK (db="bioproject") |
| SRA Sample | BioSample | EXTERNAL_ID (namespace="BioSample") |
| SRA Experiment | Study | STUDY_REF (refname or accession) |
| SRA Experiment | Sample | SAMPLE_DESCRIPTOR (refname or accession) |
| SRA Run | Experiment | EXPERIMENT_REF (refname or accession) |
| JGA Dataset | Policy | POLICY_REF (required) |
| JGA Policy | DAC | DAC_REF (required) |

RefNameGroup の 2 フェーズ:

- **登録前**: `refname` + `refcenter` で同一 submission 内のオブジェクトを参照
- **登録後**: `accession` で archive 全体のスコープで参照

#### 議論ログ: submission set の扱い

案 E の徹底により、submission set は DdbjRecord 自体で自然に表現できる:

- 1 つの DdbjRecord に BP + BS + SRA のフィールドを全部入れれば、それ自体が submission set
- 各 DB 向けの validation rules が全て通れば、API 側がそれぞれの DB に投入する
- 別々の DdbjRecord に分けて投入することもできる（API 層で束ねる）
- つまり submission set は JSON フォーマットの仕様としても API 層としても扱える

#### Open questions

- [x] ~~submission set を DdbjRecord の上位概念として定義するか~~ → 案 E により DdbjRecord 自体で表現可能。API 層でも扱える
- [ ] JGA-Dataset は submission set の一種か
  - 調査結果: Dataset は Data + Analysis をグループ化し Policy を紐付ける単位。set に近い概念
  - ただし JGA 内部の概念なので、JGA の DdbjRecord 内で表現する（cross-DB ではない）
- [ ] set 内の record 間の参照をどう解決するか
  - XSD の RefNameGroup パターン: 登録前は refname（ローカル名）、登録後は accession
  - v3 でも同様の 2 フェーズ参照が必要
  - API 層が accession 発行後に参照を解決する想定

## Status と Validation

### record-idm の 2D status model

record-idm で定義された 2 軸のステータスモデルを v3 に取り込む。

| record_status | 意味 | 許容される submission_stage |
|---------------|------|-----------------------------|
| private | 非公開 | draft, submitted, in_curation, revision_requested, accepted |
| public | 公開 | accepted |
| suppressed | 公開後抑制 | accepted |
| withdrawn | 公開後取下 | accepted |
| canceled | 公開前取消 | null, draft, submitted, in_curation, rejected |
| unregistered | accession 予約済み未登録 | null |

#### Open questions

- [ ] record_status / submission_stage を DdbjRecord のフィールドに含めるか
- [ ] status は DdbjRecord の属性か、外部メタデータか

### Validation 機構の設計

#### 議論ログ: 設計方針

eslint のアーキテクチャを参考に、以下の方針を決定:

**原則: record は純粋な data。validation config は外付け。**

```
record.json          -> pure data (what)
rules (Python)       -> validation logic (check + fix)
config (CLI/API)     -> which rules to run, at what severity (how)
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
│   ├── BP_RULES: list[Rule]
│   ├── BS_RULES: list[Rule]
│   ├── SRA_RULES: list[Rule]
│   ├── INSDC_RULES: list[Rule]
│   └── ALL_RULES: list[Rule]
└── Rule definitions (YAML data, loaded by Python rules)
    ├── insdc_feature_table.yaml
    ├── bs_packages.yaml
    └── ...
```

**Rule の Python interface:**

```python
class Rule(Protocol):
    id: str                          # "bp/title-required"
    default_severity: Severity       # error / warning

    def check(self, record, context) -> list[Diagnostic]: ...
    def fix(self, record, diagnostic) -> Record | None: ...  # optional
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

**3 つの決定事項:**

1. **record は純粋な data** — validation config を record 内に持たない
2. **rule の interface は Python に統一** — YAML は data definition（INSDC feature table 等）として使うが、rule の interface は Python class/function
3. **fix は rule ごとに optional** — eslint パターン。rule が `fix()` を提供していれば `--fix` で自動修正可能

**rule と config の責務分離:**

| 責務 | 担当 | 例 |
|------|------|-----|
| rule の定義 | this repo | `bp/title-required`, `insdc/feature-key-exists` |
| rule set の定義 | this repo | `BP_RULES`, `SRA_RULES` |
| どの rule を使うか | consumer (API / CLI / other tools) | `--rules bp,bs` |
| どの stage で検証するか | consumer | `--stage draft` |
| severity の override | consumer | `--severity bp/title-required=warning` |

### Validation の段階的挙動

validation の挙動を context に応じて切り替える。stage は consumer が外部から指定する。

| stage | 例 | validation の期待 |
|-------|-----|-------------------|
| draft | submitter がローカルで作成 | 緩い（warning 中心） |
| submission | DDBJ に提出 | 厳密（error で reject） |
| curation | DDBJ staff が編集 | 厳密 + 追加ルール |
| accepted | accession 発行済み | 変更制約あり |
| public | 外部公開済み | validation skip or 読み取り専用 |

rule 内で stage に応じて severity を切り替える:

```python
class BpTitleRequired(Rule):
    id = "bp/title-required"
    default_severity = Severity.ERROR

    def check(self, record, context):
        if record.project and not record.project.title:
            severity = (Severity.WARNING if context.stage == "draft"
                       else Severity.ERROR)
            return [Diagnostic(rule=self.id, severity=severity, ...)]
        return []
```

### Fix の設計

`--fix` で自動修正可能な操作の分類:

| fix の種類 | 例 | 安全性 |
|-----------|-----|--------|
| 正規化 | 日付フォーマット統一、空白 trim | 安全 |
| 導出 | organism → division 自動決定 | やや安全（taxonomy DB 依存） |
| デフォルト補完 | 欠落フィールドにデフォルト値 | 要注意 |
| 構造変換 | v2 → v3 マイグレーション | converter の責務 |
| curation | qualifier value の修正、organism 名の正規化 | 外部リソース依存 |

#### Open questions

- [ ] fix の安全性レベルを分類し、`--fix` のモードを分けるか（`--fix=safe`, `--fix=all` 等）
- [ ] 外部リソース依存の fix（taxonomy DB 等）をどう扱うか
- [ ] fix の結果を diff として表示する機能（dry-run）
- [ ] 公開後の record に対する validation は skip するか
- [ ] forbidden フィールドに値が入っていた場合、error か warning か

## 技術的制約

#### Open questions

- [ ] JSON ファイルサイズの実用上限（大規模ゲノムで数 GB になりうるか）
- [ ] 文字数上限（qualifier value 等）
- [ ] streaming parse の必要性（巨大 JSON）
- [ ] binary data（配列本体）を JSON に含めるか、外部ファイル参照か

## Converter 戦略

v3 の converter は双方向変換を担う。

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
- JGA XML
```

#### Open questions

- [ ] converter はこの repo に含めるか、別 repo（ddbj_record_converter）にするか
- [ ] v2 → v3 の migration converter は必要か
- [ ] round-trip 保証の範囲（全形式で保証するか、形式ごとに定義するか）
- [ ] dr_tools との関係（統合？分離？）

## ENA との関係

ENA も独自に JSON 化を進めている。

参考: <https://ena-docs.readthedocs.io/en/latest/submit/general-guide/programmatic.html>

### 既知の情報

- ENA は独自に JSON を進めており、ENA 仕様に寄っている可能性がある
- BioSample の `name` を ENA だけ `alias` という単語で運用していたことが判明し、他極（実際は minimum）に合わせて `name` に直すよう合意済み（コードは未修正の可能性）
- ENA には BioProject ではなく `study` があり、そこに BioProject を link（sameAs かは未確認）している

#### Open questions

- [ ] ENA の JSON schema を参考にするか
- [ ] alias vs name の用語整合の現状確認
- [ ] study と BioProject の link 方式（sameAs? 別の関係?）
- [ ] 3 極（DDBJ, ENA, NCBI）間でのデータ互換性をどこまで意識するか

## 未解決の論点一覧

各セクションの open questions を集約したもの。議論の進行に応じて resolved / dropped に移動する。

（各セクション内の `- [ ]` を参照）
