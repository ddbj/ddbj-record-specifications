# v3 Raw Test Data

v3 converter の変換元となる実データを収集したディレクトリ。
各サブディレクトリは DDBJ の登録種別 (データベース/フォーマット) に対応する。

converter 実装時に、ここの入力データに対応する期待出力 (DdbjRecord v3 JSON) を別途追加する想定である。

## ディレクトリ構成

```
raw/
├── bioproject/      BioProject XML
├── biosample/       BioSample XML (gzip)
├── dra/             DRA/SRA XML (accession unit)
├── jga/             JGA XML + relation CSV
├── gea/             GEA IDF/SDRF (MAGE-TAB)
├── metabobank/      MetaboBank IDF/SDRF (MAGE-TAB)
├── trad/            Traditional annotation + flat file
├── st26/            ST.26 patent sequence XML (WIPO)
├── gff/             GFF3 genome annotation
└── assembly/        Assembly report + AGP + ENA XML
```

## データ出自

### bioproject/

NCBI BioProject XML。`ddbj-search-converter` テストデータから流用。

| ファイル | 内容 | サイズ |
|---|---|---|
| `bioproject.xml` | 複数プロジェクトを含む BioProject XML (NCBI/EBI/DDBJ) | 121 KB |
| `ddbj_core_bioproject.xml` | DDBJ コアプロジェクトのみの XML | 16 KB |

スキーマ: Core.xsd, Submission.xsd

### biosample/

NCBI BioSample XML (gzip 圧縮)。`ddbj-search-converter` テストデータから流用。

| ファイル | 内容 | サイズ |
|---|---|---|
| `biosample_set.xml.gz` | 全 BioSample レコード (NCBI/EBI/DDBJ) | 3.2 KB |
| `ddbj_biosample_set.xml.gz` | DDBJ BioSample レコードのみ | 2.8 KB |

スキーマ: biosample.xsd v1.2.0

### dra/

DRA (DDBJ Sequence Read Archive) / SRA / ERA の submission 単位 XML。
`ddbj-search-converter` テストデータから流用。

accession ごとにサブディレクトリを持ち、最大 6 種の XML を格納する:
`{accession}.{submission,study,experiment,sample,run,analysis}.xml`

| prefix | accession 数 | origin |
|---|---|---|
| DRA | 10 | DDBJ |
| ERA | 10 | EBI/ENA |
| SRA | 10 | NCBI |

合計: 30 accession, 164 XML ファイル, 3.2 MB

スキーマ: SRA XML v1.6

### jga/

JGA (Japanese Genotype-phenotype Archive) のメタデータ XML と relation CSV。
`ddbj-search-converter` テストデータ + NIG スパコン本番データから取得。

#### XML メタデータ

| ファイル | 内容 | 出自 |
|---|---|---|
| `jga-study.xml` | Study メタデータ (19 KB) | ddbj-search-converter |
| `jga-dataset.xml` | Dataset メタデータ (492 KB) | ddbj-search-converter |
| `jga-policy.xml` | Access policy 定義 (6.3 KB) | ddbj-search-converter |
| `jga-dac.xml` | Data Access Committee 情報 (601 B) | ddbj-search-converter |
| `jga-experiment.xml` | Experiment メタデータ 先頭 5 件 (6.8 KB) | NIG スパコン (602 MB から抽出) |
| `jga-analysis.xml` | Analysis メタデータ 先頭 5 件 (6.7 KB) | NIG スパコン (442 MB から抽出) |
| `jga-data.xml` | Data メタデータ 先頭 5 件 (4.3 KB) | NIG スパコン (401 MB から抽出) |

#### relation CSV + date CSV

| ファイル | 出自 |
|---|---|
| `experiment-study-relation.csv`, `analysis-study-relation.csv`, `dataset-*-relation.csv`, `policy-dac-relation.csv`, `data-experiment-relation.csv` | ddbj-search-converter |
| `experiment-sample-relation.csv`, `analysis-sample-relation.csv`, `analysis-data-relation.csv` | NIG スパコン (先頭 20 行) |
| `*.date.csv`, `date.csv` | ddbj-search-converter / NIG スパコン (先頭 20 行) |

スキーマ: JGA XSD v1.2
本番データパス: `/usr/local/shared_data/jga/metadata-history/metadata/`

### gea/

GEA (Gene Expression Archive) の IDF/SDRF ファイル (MAGE-TAB 形式)。
`ddbj-search-converter` テストデータから流用。

experiment 単位のサブディレクトリに `.idf.txt` (Investigation Description) と `.sdrf.txt` (Sample and Data Relationship) を格納。

10 experiment: E-GEAD-1005, E-GEAD-1017, E-GEAD-1037, E-GEAD-1039, E-GEAD-1043, E-GEAD-1044, E-GEAD-1047, E-GEAD-1057, E-GEAD-1060, E-GEAD-1096

### metabobank/

MetaboBank の IDF/SDRF ファイル (MAGE-TAB 形式)。
`ddbj-search-converter` テストデータから流用。

study 単位のサブディレクトリに `.idf.txt` と `.sdrf.txt` を格納。

10 study: MTBKS70, MTBKS71, MTBKS85, MTBKS102, MTBKS103, MTBKS208, MTBKS232, MTBKS238, MTBKS241, MTBKS264

### trad/

Traditional (Trad) 登録の変換元データ。2 種類のフォーマットを含む。

#### DFAST annotation (.ann + .fa)

`dr_tools` リポジトリの examples/ から流用。
DFAST の出力形式であり、v3 converter の主要な入力フォーマットとなる。

| ファイル | 内容 |
|---|---|
| `complete_genome.ann` + `complete_genome.fa` | Paucilactobacillus hokkaidonensis 完全ゲノム (559 KB + 2.4 MB) |
| `vrl_result.ann` + `vrl_result.fa` | SARS-CoV-2 ウイルスゲノム (3.7 KB + 30 KB) |

#### DDBJ flat file (.seq)

DDBJ getentry API から取得した GenBank/DDBJ 形式の公開データ。
既存公開データから DdbjRecord への逆変換テストに使用する。
各登録カテゴリ (一般、WGS、TSA、TPA、complete genome) の代表サンプルを含む。

| ファイル | カテゴリ | 内容 |
|---|---|---|
| `AB000001.seq` | 一般 | Rhizoctonia solani 18S/5.8S/28S rRNA (660 bp, 2.5 KB) |
| `BBYQ01000001.seq` | WGS | Nocardia seriolae U-1 WGS contig (22,211 bp, 42 KB) |
| `IAAA01000001.seq` | TSA | Parasteatoda tepidariorum TSA contig (1,225 bp, 3.4 KB) |
| `BR000123.seq` | TPA | Ciona intestinalis TPA:experimental zinc finger protein (1,954 bp, 5.7 KB) |
| `AP013064.seq` | Complete genome | Serratia marcescens SM39 plasmid pSMC1 (41,517 bp circular, 85 KB) |

#### ORGANISM_LIST (参照メタデータ)

`ddbj-search-converter` テストデータから流用。
WGS/TSA/TLS/TPA の ORGANISM_LIST TSV ファイル。

```
organism_list/
├── wgs/WGS_ORGANISM_LIST.txt
├── tsa/TSA_ORGANISM_LIST.txt
├── tls/TLS_ORGANISM_LIST.txt
└── tpa/
    ├── wgs/TPA_WGS_ORGANISM_LIST.txt
    ├── tsa/TPA_TSA_ORGANISM_LIST.txt
    └── tls/TPA_TLS_ORGANISM_LIST.txt
```

### st26/

WIPO Standard ST.26 (特許配列リスト) の XML サンプル。
WIPO 公式サイトから取得。

| ファイル | 内容 |
|---|---|
| `annex-iii-specimen.xml` | WIPO Annex III 公式サンプル: DNA/RNA/AA 11 配列、複数生物種 (17 KB) |
| `Valid-Exemplary DNA and AA.xml` | Valid: DNA + AA 2 配列、ロシア語非英語 qualifier 付き (3.5 KB) |
| `Valid_DNA_AA_project.xml` | Valid: DNA + AA 2 配列、ラテン文字 applicant name (3.5 KB) |
| `Error-Mandatory_qualifier_MOL_TYPE_for_the_feature_SOURCE_is_missing.xml` | Error: mol_type 欠落 (3.6 KB) |
| `Error-Missing_Non_English_Qualifier_Value.xml` | Error: 非英語 qualifier 値欠落 (3.2 KB) |
| `Error-Missing_Non_English_Qualifier_Valu.xml` | Error: 非英語 qualifier 値が空 (3.6 KB) |
| `Error_The_Applicant_File_Reference_number_is_missing..xml` | Error: ApplicantFileReference 欠落 (3.5 KB) |
| `README.txt` | WIPO 提供のバリデーション結果説明 (1.7 KB) |

DTD: ST26SequenceListing_V1_3.dtd
ソース:
- Annex III: https://www.wipo.int/standards/en/xml_material/st26/
- Valid/Error: https://www.wipo.int/documents/d/standards/docs-en-wipo-sequence-valid_and_error.zip

### gff/

GFF3 (Genome Feature Format version 3) のアノテーションファイル。
NCBI RefSeq から取得。ウイルスと細菌の 2 種類を含む。

| ファイル | 内容 |
|---|---|
| `NC_001416.1.gff3` | Escherichia phage Lambda 完全ゲノム (48,502 bp, 314 行, 58 KB) |
| `NC_009937.1.gff3` | Azorhizobium caulinodans ORS 571 完全ゲノム (5.37 Mbp, 9,886 行, 2.9 MB) |

ソース:
- Lambda: NCBI Sequence Viewer (nuccore/NC_001416.1)
- Azorhizobium: NCBI FTP (GCF_000010525.1_ASM1052v1)

### assembly/

NCBI Assembly report、AGP、ENA Assembly XML の 3 形式を含む。

#### NCBI Assembly report

| ファイル | 内容 |
|---|---|
| `GCF_000010525.1_assembly_report.txt` | Azorhizobium caulinodans ORS 571 完全ゲノム (1.2 KB) |

ソース: https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/010/525/GCF_000010525.1_ASM1052v1/

#### AGP (A Golden Path)

クローンベースアセンブリのコンポーネント配置情報。NCBI FTP から取得。
C. elegans WBcel235 アセンブリの染色体 AGP (複数コンポーネントを持つ現実的なデータ)。

| ファイル | 内容 |
|---|---|
| `celegans_chrI.comp.agp` | Chromosome I: ~300 コンポーネント (26 KB) |
| `celegans_chrIII.comp.agp` | Chromosome III: ~250 コンポーネント (22 KB) |

ソース: https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/002/985/GCF_000002985.6_WBcel235/

#### ENA Assembly XML

ENA REST API から取得した Assembly XML。

| ファイル | 内容 |
|---|---|
| `GCA_000005845.2_ena_assembly.xml` | E. coli K-12 MG1655 完全ゲノム (3.8 KB) |
| `GCA_000010525.1_ena_assembly.xml` | Azorhizobium caulinodans ORS 571 完全ゲノム (3.3 KB) |

ソース: https://www.ebi.ac.uk/ena/browser/api/xml/

## 統計

| ディレクトリ | ファイル数 | サイズ |
|---|---|---|
| bioproject | 2 | 144 KB |
| biosample | 2 | 12 KB |
| dra | 164 | 3.2 MB |
| jga | 26 | 628 KB |
| gea | 20 | 240 KB |
| metabobank | 20 | 512 KB |
| trad | 15 | 3.2 MB |
| st26 | 8 | 52 KB |
| gff | 2 | 3.0 MB |
| assembly | 5 | 68 KB |
| **合計** | **264** | **11 MB** |

## TODO

以下のデータは今後必要に応じて追加する。

- [ ] GEA/MetaboBank の livelist ファイル (ローカルリポジトリに見つからなかった)
- [ ] JGA の sample XML (jga-sample.xml はスパコン上にも存在しなかった)
