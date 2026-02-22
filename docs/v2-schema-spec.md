# v2 Schema Type Constraints (v2.1)

v2.1 で追加された Pydantic モデルの型制約仕様。

## フィールド制約一覧

| フィールド | 型 | 制約 |
|---|---|---|
| `DdbjRecord.schema_version` | `str` | `^(v\d+\.\d+\|v\d+\|\d+\.\d+)$` (例: `v2.0`, `v2.1`, `v2`, `0.2`) |
| `Entry.id` | `str` | `^[a-zA-Z0-9_.\-]{1,32}$` |
| `Submission.trad_submission_category` | `Literal["WGS", "GNM"] \| None` | 列挙値のみ許可 |
| `Submission.hold_date` | `str \| None` | `^\d{4}-\d{2}-\d{2}$` (ISO 8601 日付) |
| `Reference.year` | `str` | `^(\d{4})?$` (空文字許可、unpublished 等) |
| `Reference.date_published` | `str \| None` | `^\d{4}-\d{2}-\d{2}$` (ISO 8601 日付) |

## 日付妥当性チェック

`hold_date` と `date_published` は、パターン一致に加えて `datetime.date.fromisoformat()` による実在日チェックを行う。

- `2025-02-30` → パターンは通過するが、実在しない日付のためエラー
- `2024-02-29` → 閏年なので有効
- `2025-02-29` → 非閏年のためエラー

このチェックは `validator.py` の Stage 2.5 で実行され、エラータイプは `invalid_date_value` となる。

## レガシー schema_version の扱い

`"0.2"`, `"v2"` などのレガシー値は Pydantic `field_validator` で最新 minor version (`v2.1`) に正規化される。validator.py の Stage 1 でも同じ `normalize_schema_version()` を使用する。

## v2.0 との後方互換性

v2.1 の制約は v2.0 で有効だったデータの一部を拒否する破壊的変更を含む。v2.0 データも同じモデルで検証される。
