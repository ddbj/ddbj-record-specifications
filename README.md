# DDBJ Record Specifications

DDBJ における登録用 JSON フォーマット (DDBJ Record) の仕様を定義するリポジトリ。
DFAST などの自動アノテーションツールや、Repository API により利用されることを想定している。

本リポジトリでは、以下の機能を提供する:

- **スキーマ定義**: Python (Pydantic) によるスキーマ定義と JSON Schema の生成
- **バリデーション**: DDBJ Record JSON ファイルのスキーマレベルでの検証
- **バージョン変換**: スキーマバージョン間の双方向変換 (e.g., v1↔v2)

DDBJ Record は [dr_tools](https://github.com/ddbj/dr_tools) と連携することで `ann` / `gbk` / `fasta` などへの変換が可能となる。

## Installation

```bash
pip install git+https://github.com/ddbj/ddbj-record-specifications.git@main
# OR (version specify)
pip install git+https://github.com/ddbj/ddbj-record-specifications.git@0.1.5
```

## バージョニング

本リポジトリでは、**Specification version** と **Application version** を独立して管理する。

### Specification version (スキーマ仕様のバージョン)

DDBJ Record のスキーマ仕様自体のバージョン。JSON の `schema_version` フィールドに記録する。

- 形式: `v{major}.{minor}` (e.g., `v1.0`, `v2.0`, `v2.1`)
- major: スキーマ構造の根本的な再設計。新しいスキーマファイル (e.g., `v3.py`) を作成する
- minor: 同じ設計思想の範囲内での変更 (フィールドの追加・削除・名称変更、型の調整など)。既存スキーマファイル内で更新する
  - minor の変更は後方互換とは限らない。変更内容は CHANGELOG.md に記録する

CLI やモジュール名では major 部分のみ使用する (e.g., `--version v2`, `ddbj_record.schema.v2`)。
JSON の `schema_version` フィールドには minor を含めた完全な表記 (e.g., `"v2.0"`) を記録する。

旧表記 (`"0.1"`, `"v1"`, `"0.2"`, `"v2"`) は非推奨。読み込み時の互換性は維持するが、新規データでは使用しない。

### Application version (Python パッケージのバージョン)

Python パッケージ `ddbj-record` としてのバージョン。[Semantic Versioning](https://semver.org/) に従う。

- 形式: `MAJOR.MINOR.PATCH` (e.g., `0.1.5`, `1.0.0`)
- Specification version とは独立して管理する
- 各リリースにおける変更内容は CHANGELOG.md に記録する

## スキーマ仕様

現状、以下の spec version が存在する:

- **v1.0**: DFAST 互換のレガシー形式
  - Python 定義: [`ddbj_record/schema/v1.py`](./ddbj_record/schema/v1.py)
  - JSON Schema: [`schemas/v1/ddbj_record.schema.json`](./schemas/v1/ddbj_record.schema.json)
- **v2.0**: 構造化された現行形式
  - Python 定義: [`ddbj_record/schema/v2.py`](./ddbj_record/schema/v2.py)
  - JSON Schema: [`schemas/v2/ddbj_record.schema.json`](./schemas/v2/ddbj_record.schema.json)

## Validator

スキーマに基づくバリデーションを行う。

```bash
ddbj_record_validator --version v2 --input input.json
```

出力例:

```json
{
  "valid": true,
  "errors": null
}
```

```json
{
  "valid": false,
  "errors": [
    {
      "type": "missing",
      "loc": ["COMMON", "DBLINK", "project"],
      "msg": "Field required"
    }
  ]
}
```

## Converter

スキーマバージョン間の変換を行う。

```bash
ddbj_record_converter --from v1 --to v2 --input input.json --output output.json
```

## Development

### 開発環境

```bash
# Docker
docker compose -f compose.dev.yml up -d --build
docker compose -f compose.dev.yml exec app bash

# ローカル (Python 3.9+)
pip install -e .[tests]
```

### 新たなスキーマの開発

- 新しい spec major version (e.g., v3) を開発する場合は、latest (e.g., `v2.py`) を `draft.py` としてコピーして編集する
- Converter の存在から、なるべく version 間の互換性を保つ
- バージョニングの詳細は [バージョニング](#バージョニング) を参照

### JSON Schema の生成

Pydantic モデルから JSON Schema を生成する。GitHub Actions ([`dump_schema.yml`](./.github/workflows/dump_schema.yml)) により main push 時に自動生成される。

```bash
dump_json_schema --version v1
dump_json_schema --version v2
dump_json_schema --version draft
```

### Release

```bash
bash ./release.sh <new_version>
```

## Known Limitations / Future Improvements

v2 スキーマにおける既知の設計課題と将来の改善候補を以下に記録する。

### Submission モデルの責務過多

`Submission` に登録メタデータ (submitters, references, comments, hold_date)、データ分類 (trad_submission_category, division)、命名規則 (locus_tag_prefix, seq_prefix) が混在している。将来の major version では以下のような分離を検討する:

- **Submission**: submitters, references, comments, hold_date
- **DataClassification** (または Sequences に統合): trad_submission_category, division
- **NamingConvention** (または Sequences に統合): locus_tag_prefix, seq_prefix

### Assembly 情報と Experiment の混在

v1 の `ST_COMMENT` (Assembly Method, Coverage, Sequencing Technology) を v2 では `Experiment` に格納しているが、Assembly 情報 (どうアセンブルしたか) と Experiment (何をどうシーケンスしたか) は本質的に異なる概念である。現在のコンバーターは `id: "st_comment_experiment"` というマジックストリングで Assembly 用の Experiment を判別しており、暗黙の規約に依存している。将来の major version では Assembly を独立したモデルとして分離することを検討する。

## License

[Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0). See [LICENSE](./LICENSE).
