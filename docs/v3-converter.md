# v3 Converter 仕様

DDBJ Record v3 と各形式間の変換ルール。

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

## 各形式との対応表

v3 モデルと各形式のフィールド対応。converter / validation rule 実装時に参照する。

### Project

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
| locus_tag_prefix | LocusTagPrefix (＋ @biosample_id) | - | - |
| umbrella_subtype_description | ProjectTypeTopAdmin/DescriptionSubtypeOther | - | - |
| target.* | Target (sample_scope/material/capture) + Method + Objectives | - | - |
| target.description | Target/Description | - | - |
| target.method_description | Method 本文 | - | - |
| target.data_type_descriptions | Objectives/Data 本文（data_type をキーに） | - | - |

### Sample

| v3 | BioSample | SRA Sample | JGA Sample |
|----|-----------|-----------|-----------|
| title | Title | TITLE | TITLE |
| organism | Organism (taxonomy_id, OrganismName) | SAMPLE_NAME (TAXON_ID, SCIENTIFIC_NAME) | SAMPLE_NAME (TAXON_ID) |
| attributes | Attributes (attribute_name/value/unit) | SAMPLE_ATTRIBUTES (TAG/VALUE/UNITS) | SAMPLE_ATTRIBUTES |
| package | Models | - | - |
| donor_id | - | - | DONOR_ID |
| sample_group_type | - | - | SAMPLE_GROUP_TYPE |

### Experiment

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

### Organism

| v3 | BP | BS | SRA | JGA | Trad | ST.26 |
|----|----|----|-----|-----|------|-------|
| name | OrganismName | OrganismName | SCIENTIFIC_NAME | SCIENTIFIC_NAME | organism qualifier | organism テキスト |
| taxonomy_id | Organism@taxID | Organism@taxonomy_id | TAXON_ID | TAXON_ID | /db_xref="taxon:XXX" | なし（DB側付与） |

### Date フィールド

| v3 フィールド | 対応する各形式の名称 |
|-------------|-------------------|
| submission.hold_date | BP: Hold/@release_date、SRA: HOLD/@HoldUntilDate、Trad: hold_date |
| runs[].run_date | SRA: Run/@run_date���JGA: Data/@data_acquisition_date |
| analyses[].analysis_date | SRA: Analysis/@analysis_date、JGA: Analysis/@analysis_date |
| project.publications[].date | BP: Publication/@date |

### Relations

| v2 | v3 |
|---|---|
| `submission.db_xrefs[{db, id}]` | `relations[{type: "xref", target: {db, id}}]` |
| （存在しない） | `relations[{type: "reference", target: {url}, label}]` |
| （存在しない） | `relations[{type: "child_of", target: {db, id}}]` |
| `feature.sequence_id` | `feature.sequence_id`（変更なし） |

### Sequences & Entries

| v3 | Trad | ST.26 |
|----|------|-------|
| sequences.seq_prefix | COMMON/entry | - |
| sequences.common_source | COMMON/source | - |
| entry.sequence | sequence | INSDSeq_sequence |
| entry.type | - | "PAT" 固定 |
| source feature の organism | /organism | INSDFeature (source) organism qualifier |
| source feature の mol_type | /mol_type | INSDSeq_moltype から導出 |

ST.26 の特許メタデータ（InventionTitle, ApplicantName, InventorName, ApplicationIdentification 等）は Submission モデルの拡張で対応する想定。フィールド設計の詳細は[参考資料の ST.26 セクション](#st26-wipo-standard-st26)を参照。

### Submission の責務分解（v2 → v3）

| v2 フィールド | v3 の帰属先 | 理由 |
|-----------|------------|------|
| submitters | **submission** | 提出行為のメタデータ |
| hold_date | **submission** | 提出行為のメタデータ |
| comments | **submission** | 提出行為のメタデータ |
| references | **project.publications** | 研究プロジェクトの属性 |
| keywords | **project.keywords** | 研究プロジェクトの属性 |
| locus_tag_prefix | **project.locus_tag_prefix** | BP XSD ProjectDescr に定義 |
| division | **Entry レベル or validator 導出** | アーカイブ分類 |
| trad_submission_category | **provenance.submission_category** | 変換元の分類情報 |
| seq_prefix | **sequences.seq_prefix** | 配列エントリの命名規則 |
| datatype | **provenance.submission_category に統合** | データ種別 |
| db_xrefs | **ルート直下の relations** | 外部参照 |

## Submission Set と段階的更新フロー

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

## 参考資料

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

#### ST.26 (WIPO Standard ST.26)

特許出願における塩基配列・アミノ酸配列リストを XML 形式で記述するための国際標準。
旧規格 ST.25（プレーンテキスト）を置き換え、2022 年 7 月以降の特許出願で必須。
配列データ部分は INSDC DTD のサブセットとして設計されている。

- 特許庁（JPO, KIPO → DDBJ、USPTO → GenBank、EPO → ENA）から INSDC データベースへ配列データが提供される
- `INSDSeq_division` は `"PAT"` 固定（GenBank/DDBJ の PAT division に対応）
- INSDC 間で日次データ同期が行われ、全特許配列が世界中で利用可能になる

```
ST26SequenceListing (root)
├── ApplicationIdentification?     # application ID (if filed)
│   ├── IPOfficeCode               # IP office code (WIPO ST.3)
│   ├── ApplicationNumberText      # application number
│   └── FilingDate?                # filing date
├── ApplicantFileReference?        # applicant file ref (if not filed)
├── EarliestPriorityApplicationIdentification?  # earliest priority
│   ├── IPOfficeCode
│   ├── ApplicationNumberText
│   └── FilingDate?
├── ApplicantName?                 # applicant name (languageCode required)
├── ApplicantNameLatin?            # applicant name (Latin transliteration)
├── InventorName?                  # inventor name (languageCode required)
├── InventorNameLatin?             # inventor name (Latin transliteration)
├── InventionTitle+                # invention title (per language, languageCode required)
├── SequenceTotalQuantity          # total sequence count
└── SequenceData+                  # sequence data (INSDC subset)
    └── INSDSeq
        ├── INSDSeq_length
        ├── INSDSeq_moltype        # DNA / RNA / AA
        ├── INSDSeq_division       # "PAT" fixed
        ├── INSDSeq_other-seqids?  # pat|{office}|{pub_number}|{kind}|{seq_id}
        ├── INSDSeq_feature-table?
        │   └── INSDFeature+       # source feature + annotation features
        └── INSDSeq_sequence
```

- WIPO ST.26 DTD V1.3: <https://www.wipo.int/standards/dtd/ST26SequenceListing_V1_3.dtd>
- USPTO MPEP Section 2413: <https://www.uspto.gov/web/offices/pac/mpep/s2413.html>
- DDBJ 特許データ: <https://www.ddbj.nig.ac.jp/ddbj/patent-data-e.html>
- ST.26 Annex III specimen XML: <https://www.wipo.int/standards/en/xml_material/st26/st26-annex-iii-sequence-listing-specimen.xml>

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
