# Tests

## テストデータの方針

テストデータは以下の 2 種類に分類する。

### 1. 手書きの最小 JSON（スキーマバリデーション・変換テスト用）

スキーマ定義 (Pydantic モデル) を見ながら、手動で作成する最小限の JSON ファイル。
ツール (dr_tools, converter) に依存せず、テスト対象の仕様を直接検証できる。

- 必須フィールドのみの最小構成
- DFAST ワークフロー別の典型的な構成 (DFC GNM / DFC WGS / DFV)
- 不正な値・欠損フィールドを含む異常系
- GenBank 形式由来の特殊ケース (複数 source feature、複雑な location 等)
- レガシー `schema_version` ("0.1", "v1" など) の互換性
- converter の入出力ペア

テストデータが生物学的に正しい必要はない。
スキーマの制約が正しく検証・変換されることを確認するのが目的である。

Note: sequence と location の不整合について:

トリミング fixtures (`valid_dfc_*.json`, `valid_dfv.json`) では、sequence を先頭 100bp に切り詰めている一方、entry の source_features.location や features の location はオリジナルの座標をそのまま保持している (例: `sequence` が 100bp なのに `location: "1..2277985"`)。
現在の Pydantic スキーマでは location は `str` 型のため validation は通るが、将来ロジックレベルバリデーション (sequence 長と location の整合性チェック) を追加した場合はこれらの fixtures の更新が必要になる。

### 2. 実データスナップショット（回帰テスト用）

genbank/annotation ファイルなどの既存データから、dr_tools や converter を使って生成した JSON を**スナップショットとして凍結**したもの。
リファクタリング前後で出力が変わらないことを検証する回帰テストに使う。

- 生成元: DFAST 出力 -> dr_tools で v1 JSON 化 -> converter で v2 JSON 化
- 一度コミットしたら、意図的な仕様変更がない限り変更しない
- 現行バージョンの出力を凍結するため、循環依存は発生しない

## fixtures のデータ出自

fixtures の `valid_dfc_*.json` / `valid_dfv.json` は、実データを dr_tools (`drt_ann2json`) で変換しトリミング (entries <=3, features <=5/entry, sequence <=100bp) したものである。
データの出自は以下の 2 系統に分かれる。

### ゴールデンデータ (dr_tools examples)

dr_tools リポジトリの `examples/` に同梱されているサンプル ann+fa から生成。
フィールドが全て埋まった完全なデモデータであり、リファレンスとして扱う。

| fixture | 元データ |
|---|---|
| `v1/valid_dfc_gnm.json`, `v2/valid_dfc_gnm.json` | `dr_tools/examples/complete_genome.{ann,fa}` |
| `v2/valid_dfv.json` | `dr_tools/examples/vrl_result.{ann,fa}` |

### DFAST 実行結果データ (WF テンプレート)

DFAST ワークフローの実行結果から生成。ファイル名は `valid_wf_*` プレフィックスで統一。
テンプレート状態のまま実行されたデータであり、submitter 情報・organism 等が空文字列のケースが含まれる。
これは実際の DFAST 出力の姿をそのまま反映しており、意図的に許容している。

| fixture | WF | 元データ |
|---|---|---|
| `v1/valid_wf_dfc_wgs.json`, `v2/valid_wf_dfc_wgs.json` | DFC | `mss.{ann,fasta}` |
| `v2/valid_wf_dfv.json` | DFV | `dfv/DDBJ.{annt.tsv,seq.fa}` |

VADR 単体 WF の ann+fa 出力は DFAST 実行結果に存在しなかった（VADR は DFV の内部ステップとして動作する）。

## fixtures ディレクトリ構成

### v1

v1 は DFC (dfast_core) 専用のレガシー形式。`trad_submission_category` が `Literal["WGS", "GNM"]` のため DFV データは対象外。
特殊ケース (複数 source feature 等) は v2 で作成し、converter テストで v1 との変換を検証する。

| ファイル | 内容 |
|---|---|
| `valid_minimal.json` | 必須フィールドのみの最小構成 (手書き) |
| `valid_dfc_gnm.json` | DFC 完全ゲノム (chromosome circular + plasmid)。ゴールデンデータ |
| `valid_wf_dfc_wgs.json` | DFC ドラフトゲノム (unplaced linear × 複数 contig)。WF テンプレートデータ |
| `invalid_missing_required.json` | 必須フィールドの欠損 (手書き) |
| `invalid_wrong_type.json` | Literal 値の不正 (`trad_submission_category: "VRL"`) (手書き) |
| `legacy_schema_version.json` | `schema_version: "0.1"` での読み込み互換テスト (手書き) |

### v2

v2 は現行形式。DFC / DFV の両方をカバーし、GenBank 形式由来の特殊ケースもここで扱う。

| ファイル | 内容 |
|---|---|
| `valid_minimal.json` | 必須フィールドのみの最小構成 (手書き) |
| `valid_dfc_gnm.json` | DFC 完全ゲノム (chromosome circular + plasmid circular/linear)。ゴールデンデータ |
| `valid_dfv.json` | DFV ウイルスゲノム (mol_type: genomic RNA)。ゴールデンデータ |
| `valid_wf_dfc_wgs.json` | DFC ドラフトゲノム (unplaced linear × 複数 contig)。WF テンプレートデータ |
| `valid_wf_dfv.json` | DFV ウイルス (source feature のみ)。WF テンプレートデータ |
| `valid_multi_source.json` | 1 entry に複数の source_features (キメラ配列等) (手書き) |
| `valid_complex_location.json` | join, complement(join(...)), order, fuzzy (<, >) (手書き) |
| `valid_boolean_qualifier.json` | /pseudo, /trans_splicing 等の値なし qualifier (手書き) |
| `invalid_missing_required.json` | 必須フィールドの欠損 (手書き) |
| `invalid_wrong_type.json` | Literal 値の不正 (Xref.db: "invalid_db", Entry.type: "unknown") (手書き) |
| `invalid_extra_field.json` | extra="forbid" のモデルに余計なフィールド (手書き) |
| `legacy_schema_version.json` | `schema_version: "0.2"` での読み込み互換テスト (手書き) |

### converter

converter の入出力ペア。入力を converter に通した結果が expected と一致することを検証する。
expected は `model_dump_json(exclude_none=True)` で生成している。

| ファイル | 内容 |
|---|---|
| `v1_to_v2_input.json` | v1 形式の有効な JSON (= `v1/valid_dfc_gnm.json` と同一内容) |
| `v1_to_v2_expected.json` | v1→v2 変換の期待出力 |
| `v2_to_v1_input.json` | v2 形式の有効な JSON (= `v2/valid_dfc_gnm.json` と同一内容) |
| `v2_to_v1_expected.json` | v2→v1 変換の期待出力 |
