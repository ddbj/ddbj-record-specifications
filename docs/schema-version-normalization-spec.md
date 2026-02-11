# schema_version 正規化仕様

## 背景

v2 スキーマの `schema_version` フィールドに `pattern=r"^v\d+\.\d+$"` が設定されており、`v2` や `0.2` といったレガシー値が Pydantic バリデーションで弾かれる。`description` には "Legacy values ('v2', '0.2') are accepted but deprecated" と記載されているが、実際の `pattern` と矛盾している。

現状の `LEGACY_SCHEMA_VERSION_MAP` は `v2` -> `v2.0` にマッピングしているが、最新 minor version は `v2.1` であり、レガシー値の正規化先も不適切。

## 設計方針

- **入力 (validator/converter)**: `v2`, `0.2`, `v2.0`, `v2.1` のいずれも受け付け、最新の minor version として正規化して処理する
- **出力 (converter)**: 最新の minor version を出力する (既存の動作を維持)
- **JSON Schema (pattern)**: レガシー値も含めて受け付けるパターンに緩和する

## 受け付ける schema_version 値

### v2 系

| 入力値 | 正規化後 | 備考 |
| --- | --- | --- |
| `v2.1` | `v2.1` | 現在の最新 minor version |
| `v2.0` | `v2.1` | 旧 minor version -> 最新に正規化 |
| `v2` | `v2.1` | メジャーのみ (レガシー) -> 最新に正規化 |
| `0.2` | `v2.1` | レガシー表記 -> 最新に正規化 |

### v1 系

| 入力値 | 正規化後 | 備考 |
| --- | --- | --- |
| `v1.0` | `v1.0` | 現在の最新 minor version |
| `v1` | `v1.0` | メジャーのみ (レガシー) -> 最新に正規化 |
| `0.1` | `v1.0` | レガシー表記 -> 最新に正規化 |

要するに、入力された `schema_version` が所属する major version を特定し、その major version の `LATEST_MINOR_VERSIONS` に正規化する。

## 正規化関数

`schema/__init__.py` に `normalize_schema_version()` 関数を新設する。

```python
def normalize_schema_version(raw: str) -> str | None:
    """Normalize a schema_version value to the latest minor version.

    Returns the latest minor version string (e.g., "v2.1") or None if unrecognized.
    """
```

正規化のロジック:

1. `LEGACY_SCHEMA_VERSION_MAP` にヒットする場合 -> マッピングされた major version の最新 minor version を返す
2. `v{major}.{minor}` 形式の場合 -> その major version の最新 minor version を返す
3. いずれにもマッチしない場合 -> `None` を返す

## 変更箇所

### 1. `ddbj_record/schema/__init__.py`

- `LEGACY_SCHEMA_VERSION_MAP` は **削除** する (正規化関数に統合)
- `normalize_schema_version(raw: str) -> str | None` 関数を新設する

### 2. `ddbj_record/schema/v2.py`

- `schema_version` フィールドの `pattern` を緩和:
  - 現状: `r"^v\d+\.\d+$"` (`v2.0` のみマッチ)
  - 変更後: `r"^(v\d+\.\d+|v\d+|\d+\.\d+)$"` (`v2.0`, `v2`, `0.2` すべてマッチ)
- Pydantic `field_validator` を追加し、入力値を `normalize_schema_version()` で最新 minor version に正規化する
  - 未知の値は `ValueError` を raise する
- `description` を更新して実態と整合させる

### 3. `ddbj_record/schema/v1.py`

- `schema_version` フィールドに `pattern` と `field_validator` を追加し、v2 と同様のレガシー値受け入れ・正規化を行う

### 4. `ddbj_record/validator.py`

- `_validate_schema_version_consistency()` を `normalize_schema_version()` を使うように書き換える
  - 現状 `LEGACY_SCHEMA_VERSION_MAP.get(raw_version, raw_version)` で正規化しているのを、新関数に置き換える
  - 一貫性チェックのロジック: 正規化後の値が `{schema_version}.` で始まるかチェック -> そのまま維持

### 5. テスト

- v2 スキーマのテスト: `v2`, `0.2`, `v2.0`, `v2.1` を入力したとき、すべて `v2.1` に正規化されることを確認
- v1 スキーマのテスト: `v1`, `0.1`, `v1.0` を入力したとき、すべて `v1.0` に正規化されることを確認
- `normalize_schema_version()` の単体テスト
- validator のレガシー値テスト: 既存テストの期待値を更新 (`v2.0` -> `v2.1`)
- converter のテスト: 出力の `schema_version` が最新 minor version であることを確認 (既存テスト維持)

## 変更しないもの

- `SCHEMA_VERSIONS` / `LATEST_VERSION` / `LATEST_MINOR_VERSIONS` の定義
- `normalize_cli_version()` (CLI 引数の正規化。こちらはメジャーバージョンを返す用途なので変更不要)
- converter の出力ロジック (`LATEST_MINOR_VERSIONS` を使用。既に期待通りの動作)
- `resolve_record_model()` (メジャーバージョンからモデル解決。変更不要)
