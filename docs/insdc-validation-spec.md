# INSDC Feature/Qualifier バリデーション仕様

DDBJ Record の validator に INSDC feature/qualifier テーブルとの照合機能を追加する仕様を定義する。

## 目的

feature の `type` と qualifier の名前は意図的に `str`（enum にしていない）ため、タイポや不正な値を検出できない。INSDC の公式定義に基づくバリデーションでこれを解決する。

## バリデーションの位置付け

既存の 3 段階バリデーションの後に第 4 段階として追加する。

1. schema_version 整合性チェック
2. スキーマバリデーション（Pydantic）
3. 参照整合性バリデーション
4. **INSDC feature/qualifier バリデーション** (NEW)

第 3 段階まで通過した場合のみ第 4 段階を実行する。

## データソース

INSDC/DDBJ の公式ドキュメントを唯一のデータソースとする。

| ソース | 内容 | URL |
|---|---|---|
| Feature/Qualifier マトリックス (Google Sheets) | feature ごとの qualifier 対応表 | <https://docs.google.com/spreadsheets/d/1qosakEKo-y9JjwUO_OFcmGCUfssxhbFAm5NXUAnT3eM/> |
| DDBJ Feature Key リファレンス | feature key の定義・説明 | <https://www.ddbj.nig.ac.jp/ddbj/features.html> |
| DDBJ Qualifier Key リファレンス | qualifier の value format・controlled vocabulary | <https://www.ddbj.nig.ac.jp/ddbj/qualifiers.html> |
| INSDC Feature Table Definition | 公式仕様書（Version 11.3, Oct 2024） | <https://www.insdc.org/submitting-standards/feature-table/> |

## 定義データ (`insdc_feature_table.yaml`)

公式ソースから生成した YAML ファイルを `ddbj_record/insdc/` に配置する。

### 構造

```yaml
meta:
  insdc_version: "11.3"
  generated_at: "2026-02-11T00:00:00Z"
  sources: [...]

qualifiers:
  <qualifier_name>:
    value_format: "text" | "controlled_vocabulary" | "none" | "structured"
    description: "..."
    controlled_vocabulary: [...]  # controlled_vocabulary の場合のみ
    deprecated:                   # deprecated の場合のみ
      replacement: "..."
      message: "..."
    regex: "..."                  # バリデーション用正規表現（任意）

features:
  <feature_name>:
    description: "..."
    qualifiers:
      <qualifier_name>: "mandatory" | "optional"

cross_constraints:
  - type: "mutual_exclusion" | "dependency" | "exclusion" | "conditional_mandatory"
    ...
```

### qualifier の value_format 分類

| Format | 説明 | 例 |
|---|---|---|
| `text` | 自由記述テキスト | `/product`, `/gene`, `/note` |
| `controlled_vocabulary` | 選択肢から選ぶ | `/codon_start`, `/mol_type`, `/gap_type` |
| `none` | 値なし（boolean フラグ） | `/pseudo`, `/environmental_sample` |
| `structured` | 特定の構造化フォーマット | `/inference`, `/anticodon`, `/lat_lon` |

## ErrorDetail の拡張

```python
class ErrorDetail(BaseModel):
    type: str
    loc: list[str | int]
    msg: str
    severity: Literal["error", "warning"] = "error"
    context: dict[str, Any] | None = None
    stage: str | None = None
```

### フィールド説明

| フィールド | 説明 |
|---|---|
| `type` | エラー種別（`unknown_feature_key`, `missing_mandatory_qualifier` 等） |
| `loc` | JSON パス（`["features", 0, "qualifiers", "product"]`） |
| `msg` | 人間が読めるメッセージ |
| `severity` | `"error"` または `"warning"`。型安全のため `Literal` を使用 |
| `context` | エラー種別固有の構造化メタデータ（後述） |
| `stage` | エラー発生段階の識別子（後述） |

### stage 一覧

| stage 値 | 対応段階 |
|---|---|
| `"schema_version"` | 段階 1: schema_version 整合性チェック |
| `"schema"` | 段階 2: Pydantic スキーマバリデーション（JSON パースエラー含む） |
| `"referential_integrity"` | 段階 3: 参照整合性チェック |
| `"insdc"` | 段階 4: INSDC feature/qualifier バリデーション |

### context 仕様（エラー種別ごと）

| エラー種別 | context キー | 説明 |
|---|---|---|
| `invalid_qualifier_value`（CV） | `allowed_values: list[str]`, `current_value: str` | 許可される値のリストと現在の値 |
| `deprecated_qualifier` | `replacement: str` | 代替として推奨される qualifier 名（存在する場合） |
| `constraint_violation`（mutual_exclusion） | `conflicting_qualifiers: list[str]` | 同時使用された競合 qualifier のリスト |

## ValidationResult の拡張

```python
class ValidationSummary(BaseModel):
    error_count: int = 0
    warning_count: int = 0

class ValidationResult(BaseModel):
    valid: bool
    errors: list[ErrorDetail] = []
    submittable: bool  # computed: error が 0 なら True
    summary: ValidationSummary  # computed: error/warning の集計
```

- `valid`: error が 0（warning のみなら `True`）← 現行ロジック
- `submittable`: error が 0（warning のみなら `True`）← `valid` と同義（将来分離予定）
- `summary`: `error_count` / `warning_count` のトップレベル集計
- `submittable` と `summary` は `@computed_field` で `errors` リストから自動導出
- warning は `errors` リストに含まれるが、`valid` / `submittable` に影響しない

### Pydantic loc 正規化

Pydantic v2 が生成する内部マーカー（`function-after[...]`, `function-wrap[...]`, `function-before[...]`）は loc から除去される。フロントエンドが受け取る loc は純粋な JSON パスのみ。

## strict / lenient モード

| モード | 未知の feature key | 未知の qualifier key | その他 |
|---|---|---|---|
| lenient（デフォルト） | warning | warning | error |
| strict | error | error | error |

lenient がデフォルトの理由: INSDC 定義ファイルに未掲載の DDBJ 独自拡張 qualifier を許容するため。

## バリデーション項目

### Phase 1: Feature Key バリデーション

feature の `type` が INSDC 定義に存在するかを検証する。

- 対象: `features[].type`（v2）、`ENTRIES[].features[].type`（v1、type != "source"）
- unknown feature key: strict=error, lenient=warning
- error type: `unknown_feature_key`

### Phase 2: Qualifier Key バリデーション

feature ごとの qualifier 許可リスト・必須リストを検証する。

- **未知の qualifier**: feature の定義にない qualifier key
  - strict=error, lenient=warning
  - error type: `unknown_qualifier_key`
- **必須 qualifier の欠如**: mandatory 指定の qualifier が存在しない
  - error type: `missing_mandatory_qualifier`
  - loc: `[..., "qualifiers", "<qualifier_name>"]`（欠如している qualifier 名を含む）
  - conditional mandatory（cross_constraints で定義）も含む
- **deprecated qualifier の使用**: deprecated 指定の qualifier を検出
  - 常に warning
  - warning type: `deprecated_qualifier`

source feature の必須 qualifier（`collection_date`, `geo_loc_name`）について:

- v2 では `organism` と `mol_type` は Pydantic スキーマで強制済み
- `collection_date` と `geo_loc_name` の欠如は warning（テストデータでは省略されうるため）

### Phase 3: Value Format バリデーション

qualifier の値が定義されたフォーマットに適合するかを検証する。

- **controlled_vocabulary**: 値が定義済みリストに含まれるか
  - error type: `invalid_qualifier_value`
- **regex**: 値が定義済み正規表現にマッチするか
  - error type: `invalid_qualifier_value`
- **none (boolean)**: v2 では値が `"true"` であること
  - error type: `invalid_qualifier_value`
- **cross-qualifier constraints**: 相互排他、依存関係
  - error type: `constraint_violation`

### v2 のバリデーション対象

| 対象 | パス | バリデーション内容 |
|---|---|---|
| 一般 feature | `features[]` | feature key + qualifier key/value |
| 共通 source | `sequences.common_source.qualifiers` | source qualifier key/value |
| Entry source | `sequences.entries[].source_features[].source.qualifiers` | source qualifier key/value |

### v1 のバリデーション対象

| 対象 | パス | バリデーション内容 |
|---|---|---|
| feature | `ENTRIES[].features[]` | feature key + qualifier key/value |

v1 の source feature は `ENTRIES[].features[]` 内の `type == "source"` で判別する。

## CLI 拡張

```
ddbj_record_validator --version v2 --input data.json [--no-insdc-validation] [--strict] [--no-fail-fast]
```

| フラグ | 説明 |
|---|---|
| `--no-insdc-validation` | INSDC バリデーションをスキップ |
| `--strict` | 未知の feature/qualifier を error にする |
| `--no-fail-fast` | Stage 3-4 のエラーを集約して返す（デフォルトは最初のエラーで停止） |

## cross_constraints の定義

Discriminated Union により型ごとに分離されたモデルを使用する。各型は `type` フィールドで識別される。

| type | モデル名 | 説明 | 例 |
|---|---|---|---|
| `mutual_exclusion` | `MutualExclusionConstraint` | 指定された qualifier は同時に使用不可 | germline, rearranged |
| `dependency` | `DependencyConstraint` | ある qualifier を使うには別の qualifier が必要 | metagenome_source -> environmental_sample |
| `conditional_mandatory` | `ConditionalMandatoryConstraint` | 条件付きで必須になる qualifier | CDS: pseudo/pseudogene なしなら product 必須 |

`CrossConstraint` は上記3型の Discriminated Union（`Annotated[... | ..., Discriminator("type")]`）として定義される。

旧 `exclusion` 型は `mutual_exclusion` に統合された（処理が同一のため）。

## fail_fast オプション

`validate_json_data` に `fail_fast: bool = True` パラメータが追加された。

- `fail_fast=True`（デフォルト）: Stage 3（referential integrity）でエラーがあれば Stage 4（INSDC）をスキップする
- `fail_fast=False`: Stage 3 のエラーがあっても Stage 4 を実行し、全エラーを集約して返す
- Stage 1（schema_version）と Stage 2（schema）は常に即 return（後続処理が不可能なため）

CLI: `--no-fail-fast` フラグで `fail_fast=False` を指定可能。

## 将来計画: Location 構文バリデーション

INSDC location 文字列（`1..100`, `complement(join(1..30,50..70))` 等）の構文検証を段階 5 として追加する構想がある。現時点では未実装。

### 概要

- Biopython の `Bio.SeqFeature.Location.fromstring()` を利用して location 文字列をパース
- **デフォルト OFF**（opt-in）。計算コストと外部依存（Biopython）を考慮
- CLI: `--location-validation` フラグで有効化
- API: `location_validation: bool = False` パラメータで有効化

### 検証項目

| 項目 | 説明 | severity |
|---|---|---|
| 構文チェック | INSDC location syntax に準拠しているか | error |
| 位置整合性 | start <= end（complement 以外） | error |
| sequence 長超過 | location の位置が sequence 長を超えていないか | error |

### 対象

- `features[].location`
- `sequences.entries[].source_features[].location`

### stage 値

`"location"`（段階 5）

### エラー種別（案）

| type | 説明 |
|---|---|
| `invalid_location_syntax` | INSDC location syntax のパースに失敗 |
| `invalid_location_range` | 位置の範囲が不正（start > end 等） |
| `location_exceeds_sequence_length` | location が sequence 長を超過 |

## 将来計画: INSDC 定義データ拡充 & structured value バリデーション

INSDC 定義の拡張と structured qualifier の値検証を追加する構想がある。現時点では未実装。

### Qualifier regex パターン拡充

YAML の `regex` フィールド（手管理、再生成時に保持される）にパターンを追加する。既存の `_validate_qualifier_values` の regex チェックがそのまま利用可能。

対象候補（優先度順）:

| qualifier | フォーマット | regex 案 |
|---|---|---|
| `lat_lon` | `DD.DD N/S DD.DD E/W` | `^\d+(\.\d+)?\s+[NS]\s+\d+(\.\d+)?\s+[EW]$` |
| `collection_date` | ISO 8601 + missing 値 | `^\d{4}(-\d{2}(-\d{2})?)?$\|^missing(:.+)?$` |
| `EC_number` | `n.n.n.n`（ワイルドカード可） | `^\d+\.\d+\.\d+\.(\d+\|-)$` |
| `locus_tag` | prefix_id 形式 | `^[A-Za-z][A-Za-z0-9_]+_[A-Za-z0-9_]+$` |

### Cross-constraint 追加

`generate_insdc_definition.py` の `CROSS_CONSTRAINTS` 定数に追加する。

追加候補:

| type | 内容 |
|---|---|
| `conditional_mandatory` | ncRNA: `ncRNA_class` は mandatory |
| `mutual_exclusion` | `environmental_sample` と `strain` の共存不可 |
| `dependency` | CDS + `transl_table` → `codon_start` 推奨 |

### Structured value バリデーション

`QualifierDefinition` に `structured_format` フィールドを追加し、サブフィールド単位の検証を行う案。

対象候補:

| qualifier | フォーマット | 例 |
|---|---|---|
| `lat_lon` | 10 進度数 | `35.68 N 139.77 E` |
| `collection_date` | ISO 8601 バリアント | `2025`, `2025-01`, `2025-01-15` |
| `inference` | `TYPE:evidence_basis` | `ab initio prediction:Prodigal:2.6` |
| `anticodon` | `(pos:location,aa:amino_acid,seq:sequence)` | `(pos:34..36,aa:Met,seq:cat)` |
| `transl_except` | `(pos:location,aa:amino_acid)` | `(pos:213..215,aa:Sec)` |

管理方式（YAML 手管理 vs スクリプト内ハードコード）の設計判断が必要。
