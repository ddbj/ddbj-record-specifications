# DDBJ Record Specifications

DDBJ における登録用 JSON フォーマット (DDBJ Record) の仕様を定義するリポジトリ。
DFAST などの自動アノテーションツールや、Repository API により利用されることを想定している。

本リポジトリでは、以下の機能を提供する:

- **スキーマ定義**: Python (Pydantic) によるスキーマ定義と JSON Schema の生成
- **バリデーション**: DDBJ Record JSON ファイルのスキーマレベルでの検証
- **バージョン変換**: スキーマバージョン間の双方向変換 (e.g., v1<->v2)

DDBJ Record は [dr_tools](https://github.com/ddbj/dr_tools) と連携することで `ann` / `gbk` / `fasta` などへの変換が可能となる。

## Installation

```bash
pip install git+https://github.com/ddbj/ddbj-record-specifications.git@main
# OR (version specify)
pip install git+https://github.com/ddbj/ddbj-record-specifications.git@0.2.0
```

## バージョニング

本リポジトリでは、**Specification version** と **Application version** を独立して管理する。

### Specification version (スキーマ仕様のバージョン)

DDBJ Record のスキーマ仕様自体のバージョン。JSON の `schema_version` フィールドに記録する。

- 形式: `v{major}.{minor}` (e.g., `v1.0`, `v2.0`, `v2.1`)
- major: スキーマ構造の根本的な再設計。新しいスキーマファイル (e.g., `v3.py`) を作成する
- minor: 同じ設計思想の範囲内での変更 (フィールドの追加・削除・名称変更、型の調整など)。既存スキーマファイル内で更新する
  - minor の変更は後方互換とは限らない。変更内容は GitHub Release に記録する

CLI やモジュール名では major 部分のみ使用する (e.g., `--version v2`, `ddbj_record.schema.v2`)。
JSON の `schema_version` フィールドには minor を含めた完全な表記 (e.g., `"v2.0"`) を記録する。

旧表記 (`"0.1"`, `"v1"`, `"0.2"`, `"v2"`) は非推奨。読み込み時の互換性は維持するが、新規データでは使用しない。

### Application version (Python パッケージのバージョン)

Python パッケージ `ddbj-record` としてのバージョン。[Semantic Versioning](https://semver.org/) に従う。

- 形式: `MAJOR.MINOR.PATCH` (e.g., `0.2.0`, `1.0.0`)
- git tag が single source of truth (hatch-vcs により自動解決)
- Specification version とは独立して管理する
- 各リリースにおける変更内容は GitHub Release に記録する

## スキーマ仕様

現状、以下の spec version が存在する:

| Version | 概要 | Python 定義 | 仕様書 |
|---|---|---|---|
| v1.0 | DFAST 互換のレガシー形式 | [`ddbj_record/schema/v1.py`](./ddbj_record/schema/v1.py) | - |
| v2.0 | 構造化された現行形式 | [`ddbj_record/schema/v2.py`](./ddbj_record/schema/v2.py) | [`docs/v2-schema.md`](./docs/v2-schema.md) |
| v3.0 | 全形式統一フォーマット（設計中） | - | [`docs/v3-schema.md`](./docs/v3-schema.md) |

v3 は全登録形式（Trad, BioProject, BioSample, SRA, JGA, ST.26, GFF, Assembly）を統一的に扱う新フォーマットとして `record-v3` ブランチで設計を進めている。詳細は [v3 スキーマ仕様](./docs/v3-schema.md)、[v3 Validator 仕様](./docs/v3-validator.md)、[v3 Converter 仕様](./docs/v3-converter.md) を参照。

JSON Schema は [GitHub Release](https://github.com/ddbj/ddbj-record-specifications/releases) からダウンロードするか、ローカルで `uv run dump_json_schema --version v1` / `--version v2` で生成する。

## Validator

スキーマに基づくバリデーションを行う。詳細は [Validator 機能仕様](./docs/v2-validator.md) を参照。

```bash
ddbj_record_validator --version v2 --input input.json
```

## Converter

スキーマバージョン間の変換を行う。詳細は [Converter 機能仕様](./docs/v2-converter.md) を参照。

```bash
ddbj_record_converter --from v1 --to v2 --input input.json --output output.json
```

## Development

### 開発環境

```bash
# Docker
docker compose up -d --build
docker compose exec app bash

# ローカル (Python 3.10+)
uv sync --extra tests
```

### テスト

テストの構成・テストデータの方針については [tests/README.md](./tests/README.md) を参照。

```bash
uv run pytest
```

### 新たなスキーマの開発

- 新しい spec major version (e.g., v3) を開発する場合は、latest (e.g., `v2.py`) を `draft.py` としてコピーして編集する
- Converter の存在から、なるべく version 間の互換性を保つ
- バージョニングの詳細は [バージョニング](#バージョニング) を参照

### JSON Schema の生成

Pydantic モデルから JSON Schema を生成する。

```bash
uv run dump_json_schema --version v1
uv run dump_json_schema --version v2
uv run dump_json_schema --version draft
```

### Release

1. 必要に応じて `ddbj_record/schema/` 内の `schema_version` を変更する
2. タグを打って push する:

```bash
git tag 0.2.0 && git push origin 0.2.0
```

CI が以下を自動実行する:

- wheel / sdist のビルド
- Docker イメージのビルドと ghcr.io への push
- JSON Schema の生成
- GitHub Release の作成 (wheel, sdist, JSON Schema を添付)

## Known Limitations / Future Improvements

v2 スキーマにおける既知の設計課題。v3 で解決予定。

### Submission モデルの責務過多

`Submission` に登録メタデータ、データ分類、命名規則が混在している。v3 では Submission を thin 化し、各情報を適切なモデル（Project, Sequences, Provenance）に分離する。詳細は [v3 Converter 仕様の責務分解表](./docs/v3-converter.md#submission-の責務分解v2--v3) を参照。

### Assembly 情報と Experiment の混在

v2 では `ST_COMMENT` を `Experiment` に格納しているが、Assembly と Experiment は本質的に異なる概念である。v3 では Assembly を独立モデルとし、ST_COMMENT は `Sequences.structured_comments` に移動する。

## License

[Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0). See [LICENSE](./LICENSE).
