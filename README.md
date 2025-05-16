# DDBJ Record Specifications

DDBJ における登録用 JSON フォーマット (DDBJ Record) の仕様を定義するリポジトリです。
この仕様は、DFAST などの自動アノテーションツールや、Repository API により利用されることを想定しています。

## 概要

本リポジトリでは、以下の内容を取り扱います:

- DDBJ Record の JSON Schema による定義
- Feature / Qualifier の仕様とバリデーションルール
- スキーマレベルを超えた追加的なバリデーションロジック
- バリデーションユーティリティのための補助 JSON 定義

DDBJ Record は、`ann` / `gbk` / `fasta` などのフォーマットへ変換可能であり、[dr_tools](https://github.com/ddbj/dr_tools) と連携することでファイル生成が可能です。

## スキーマ仕様

現在、以下の 2 つのバージョンが存在します。

- **v1.0**: 現在運用中のスキーマ
- **v2.0**: 次期バージョンとして検討中のスキーマ

各バージョンの JSON Schema は `/schemas` ディレクトリ以下に格納されています。

## Feature / Qualifier 定義

INSDC の定義 ([公式リンク](https://www.insdc.org/submitting-standards/feature-table)) に準拠しつつ、以下の形式で補助情報を定義します:

- `features.json`: 各 Feature が必須/任意で持つ Qualifier の一覧
- `qualifiers.json`: 各 Qualifier の値の形式・制約 (例: フリーテキスト、列挙値、正規表現など)

これらは `feature_table/` ディレクトリに格納されています。

## バリデーション

本リポジトリでは、以下の2段階でのバリデーションを想定しています：

1. **JSON Schema による構造的検証**
2. **スキーマを超えたロジックレベルでの検証** (例: 必須 qualifier の存在チェック、特定組み合わせの制約など)

追加のバリデーションは、`features.json` / `qualifiers.json` の情報を用いて、バリデータツール (将来的には API または CLI) で実行されます。

### バリデーション出力形式 (案)

```json
{
  "valid": false,
  "errors": [
    {
      "path": "features[3].qualifiers.organism",
      "message": "Qualifier 'organism' is required for feature 'source'"
    }
  ]
}
```

## ユーティリティスクリプト

- scripts/parse_feature_table.py: INSDC HTML 仕様から `features.json` / `qualifiers.json` を自動生成
- その他、スキーマの生成や変換に関わる補助スクリプトを随時追加予定

## 今後の展望

- v2.0 スキーマの確定と公開
- 単体 CLI バリデータの提供 (単一バイナリまたは Python CLI)
- API Server 形式でのバリデーションサービスの提供

## License

This project is licensed under [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0).
See the [LICENSE](./LICENSE) file for details.
