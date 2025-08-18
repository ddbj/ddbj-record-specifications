# DDBJ Record Specifications

DDBJ における登録用 JSON フォーマット (DDBJ Record) の仕様を定義するリポジトリ。
この仕様は、DFAST などの自動アノテーションツールや、Repository API により利用されることを想定している。

## Installation

```bash
python3 -m pip install git+https://github.com/ddbj/ddbj-record-specifications.git@main
# OR (version specify)
python3 -m pip install git+https://github.com/ddbj/ddbj-record-specifications.git@0.1.0

# Then, check the installation
python3 -c "import ddbj_record"
```

## 概要

本リポジトリでは、以下の内容を取り扱う:

- Python の pydantic による schema 定義
  - これを main file として、JSON Schema を生成する
  - Python の型定義として、周辺ツールなどで使用されることを想定している
- DDBJ Record の validator
  - JSON file を入力とする
  - 基本的に schema level の validation
  - Feature / Qualifier の仕様に基づく validation も実装予定 (現状、コード断片しか存在しない)
  - スキーマレベルを超えた追加的なバリデーションロジックも書けるようにする予定
- DDBJ Record の converter
  - 例えば、v1 から v2 へ変換するための converter

DDBJ Record は、`ann` / `gbk` / `fasta` などのフォーマットへ変換可能であり、[dr_tools](https://github.com/ddbj/dr_tools) と連携することでファイル生成が可能となる。

## スキーマ仕様

現状、以下の 2 つのバージョンが存在する

- **v1**
  - Python 定義: <https://github.com/ddbj/ddbj-record-specifications/blob/main/ddbj_record/schema/v1.py>
  - JSON Schema: <https://github.com/ddbj/ddbj-record-specifications/blob/main/schemas/v1/ddbj_record.schema.json>
- **v2**
  - Python 定義: <https://github.com/ddbj/ddbj-record-specifications/blob/main/ddbj_record/schema/v2.py>
  - JSON Schema: <https://github.com/ddbj/ddbj-record-specifications/blob/main/schemas/v2/ddbj_record.schema.json>

## Validator

2段階でのバリデーションを想定している:

- **JSON schema level の validation**
  - 型チェックや必須フィールドのチェックなど
- **スキーマを超えたロジックレベルでの validation**
  - 必須 feature / qualifier のチェック
  - 特定組み合わせの制約など

```bash
ddbj_record_validator --version v2 --input input.json
```

validation 結果の出力は、以下のような json となる:

```bash
$ ddbj_record_validator -v v1 --input ./tests/ddbj_record_v1_trimmed.failed.json 
{
  "valid": false,
  "errors": [
    {
      "type": "missing",
      "loc": [
        "COMMON",
        "DBLINK",
        "project"
      ],
      "msg": "Field required"
    },
    {
      "type": "missing",
      "loc": [
        "COMMON",
        "DBLINK",
        "biosample"
      ],
      "msg": "Field required"
    }
  ]
}
$ ddbj_record_validator -v v1 --input ./tests/ddbj_record_v1_trimmed.json
{
  "valid": true,
  "errors": null
}
```

## Converter

```bash
ddbj_record_converter --from v1 --to v2 --input input.json --output output

# Example: Convert v1 to v2
ddbj_record_converter --from v1 --to v2 --input ./tests/ddbj_record_v1_trimmed.json --output ./tests/ddbj_record_v2_trimmed.converted.json
```

## Development

### 開発環境

開発環境として、docker を用いている

```bash
docker compose -f compose.dev.yml up -d --build
docker compose -f compose.dev.yml exec app bash
```

また、docker では、`python 3.12` を用いているが、`python 3.9` 以上であればおそらく動くはず。

```bash
python -m pip install -e .[tests]
```

### 新たな schema の追加・開発

- Semantic Versioning は基本的に行わない
- 共通の編集点として、`draft.py` のようなファイルを latest (e.g., `v2.py`) からコピーして、編集を行う
  - つまり、v2 の minor version を上げるのではなく、draft を編集して、新たな major version (e.g., v3) を release する
  - Converter の存在から、なるべく、version 間の互換性を保つようにする
- schema の version と python package としての version は別物として扱う

### JSON Schema の生成方法

```bash
# ./ddbj_record/schema/v1.py より、./schemas/v1/ddbj_record.schema.json を生成する
dump_json_schema --version v1
dump_json_schema --version v2
dump_json_schema --version draft
```

### Feature / Qualifier 定義

**まだ実験的に実装中**

INSDC の定義 ([公式リンク](https://www.insdc.org/submitting-standards/feature-table)) に準拠しつつ、以下の形式で補助情報を定義する:

- `features.json`: 各 Feature が必須/任意で持つ Qualifier の一覧
- `qualifiers.json`: 各 Qualifier の値の形式・制約 (例: フリーテキスト、列挙値、正規表現など)

これらの json を `ddbj_record/feature_table` ディレクトリ以下に格納する。

### Release

```bash
bash ./release.sh <new_version>
```

## License

This project is licensed under [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0).
See the [LICENSE](./LICENSE) file for details.
