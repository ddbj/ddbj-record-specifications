# Validator 機能仕様

DDBJ Record の JSON データに対するバリデーション仕様を定義する。

## バリデーションの流れ

バリデーションは以下の 3 段階で行われ、各段階が失敗した場合は後続をスキップする。

1. **schema_version 整合性チェック** - データの schema_version と指定バージョンの一致を検証
2. **スキーマバリデーション** - Pydantic モデルによる構造・型・制約の検証
3. **参照整合性バリデーション** - フィールド間の参照関係の検証

## バリデーション結果

```json
{
  "valid": true,
  "errors": []
}
```

```json
{
  "valid": false,
  "errors": [
    {
      "type": "missing",
      "loc": ["sequences", "common_source", "organism"],
      "msg": "Field required"
    }
  ]
}
```

- `valid=true` のとき `errors` は空リスト
- `valid=false` のとき `errors` は 1 件以上
- エラーメッセージは英語

## 第 1 段階: schema_version 整合性チェック

入力データの `schema_version` が指定バージョンと整合するかを検証する。

- `schema_version` キーが存在しない場合はこのチェックをスキップ (スキーマバリデーション段階で `missing` エラーになる)
- レガシー値は正規化する (`"0.1"` -> `"v1.0"`, `"0.2"` -> `"v2.1"`, `"v1"` -> `"v1.0"`, `"v2"` -> `"v2.1"`)
- 正規化後の値が指定バージョンのプレフィックスで始まるかをチェック

| 指定バージョン | schema_version | 結果 |
|---|---|---|
| `v2` | `"v2.0"` | OK |
| `v2` | `"0.2"` (-> `"v2.1"`) | OK |
| `v2` | `"v1.0"` | NG (`schema_version_mismatch`) |

## 第 2 段階: スキーマバリデーション

Pydantic v2 モデルによる構造・型・制約の検証。必須フィールド、型一致、Literal 制約、余分なフィールドなどをチェックする。

### extra フィールドポリシー

| 設定 | 動作 | 該当モデル |
|---|---|---|
| `forbid` | 未定義フィールドがあるとエラー | v2 の大半のモデル、v1 Entry/DdbjRecord |
| `allow` | 未定義フィールドを許容して保持 | v2 Provenance, v1 CommonSource |
| `ignore` | 未定義フィールドを許容して無視 | v1 の大半のモデル |

v1 で `ignore` を多用する理由: レガシースキーマのため、古いツールが付けた余分なフィールドとの互換性を維持する。

### schema_version の正規化

レガシー値の正規化は第 1 段階と Pydantic `field_validator` の両方で `normalize_schema_version()` を使用して行う。

## 第 3 段階: 参照整合性バリデーション

スキーマバリデーション通過後に、フィールド間の参照関係を検証する。

### entry ID の一意性 (v1, v2)

`entries[].id` が重複していないこと。エラー種別: `duplicate_entry_id`

### feature ID の一意性 (v1, v2)

レコード全体で `features[].id` が重複していないこと。エラー種別: `duplicate_feature_id`

### feature.sequence_id の参照先存在 (v2 のみ)

`features[].sequence_id` が `entries[].id` のいずれかと一致すること。空文字もエラー。エラー種別: `invalid_sequence_id_reference`

### entry 内の source feature 存在 (v1 のみ)

各 entry に `type == "source"` の feature が最低 1 つ存在すること。エラー種別: `missing_source_feature`

### entry 内の source feature 存在 (v2)

各 entry の `source_features` が空リストでないこと。エラー種別: `missing_source_feature`

## 第 4 段階: INSDC feature/qualifier バリデーション

INSDC 公式定義に基づく feature key、qualifier key、qualifier value のバリデーション。詳細は `docs/insdc-validation-spec.md` を参照。

### 検証項目

- feature key の存在チェック
- qualifier key の許可リスト・必須リストチェック
- qualifier value の controlled vocabulary・boolean・regex チェック
- cross-qualifier constraints（相互排他、依存関係）

### strict / lenient モード

- **lenient（デフォルト）**: 未知の feature/qualifier key は warning
- **strict**: 未知は error

### ErrorDetail.severity

第 4 段階では `severity` フィールドを使用する。

- `"error"`: `valid=false` の判定に影響する
- `"warning"`: `valid` に影響しない（`errors` リストには含まれる）

## 未実装の検証 (将来課題)

- location 文字列の構文検証
- sequence 長さと location の整合性

## CLI (`ddbj_record_validator`)

### 引数

| 引数 | 必須 | デフォルト | 説明 |
|---|---|---|---|
| `-v`, `--version` | No | 最新バージョン (`v2`) | スキーマバージョン |
| `-i`, `--input` | Yes | - | 入力 JSON ファイルパス |
| `--no-insdc-validation` | No | `false` | INSDC バリデーションをスキップ |
| `--strict` | No | `false` | 未知の feature/qualifier を error にする |

`--version` は major version (`v1`, `v2`) に加え、minor version 付き (`v1.0`, `v2.0`) も受け付ける。minor version 付きの場合は major version に正規化される (例: `v2.0` → `v2`)。

### 処理フロー

1. JSON 読み込み
2. `validate_json_data()` でバリデーション (3 段階全て)
3. 結果を ValidationResult の JSON として stdout に出力

### exit code

| ケース | exit code |
|---|---|
| バリデーション成功 | 0 |
| バリデーション失敗 | 1 |
| JSON パースエラー | 1 (ValidationResult JSON を stdout に出力) |
| 引数エラー (不正バージョン、ファイル不存在) | 2 |
| その他の例外 | 1 |
