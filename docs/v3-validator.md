# v3 Validator 仕様

DDBJ Record v3 の validation 機構とバリデーションルールの仕様。

## 基本方針: well-formed と valid の分離

XML の設計における well-formed / valid の区別を借用する。

| レベル | 検証内容 | 担保する層 |
|---|---|---|
| well-formed | JSON としてパース可能で、スキーマの型制約に適合する | JSON Schema / Pydantic モデル |
| valid | 特定のデータ形式（ST.26, TradAnnotation 等）として意味的に正しい | バリデーションルール |

JSON Schema（Pydantic モデル）は well-formed の検証に徹する。すべての形式固有フィールドを `T | None` とし、どの形式のデータでもパース可能にする。形式固有の「このフィールドは必須」「このフィールドは禁止」は valid の検証に委ねる。

### 具体例: ST.26 record のバリデーション

以下の JSON が入力された場合を考える:

```json
{
  "schema_version": "v3.0",
  "provenance": {
    "source_format": "ST26"
  },
  "submission": {
    "submitters": [{"name": "Taro Yamada"}],
    "invention_title": null,
    "trad_submission_category": "WGS"
  }
}
```

この JSON は well-formed である（型制約に適合する）。しかし、`source_format` が `"ST26"` であるにもかかわらず:

- `invention_title` が `null` — ST.26 では必須
- `trad_submission_category` に値がある — ST.26 では使わないフィールド

バリデーション結果:

```json
{
  "valid": false,
  "errors": [
    {
      "type": "format_required_field_null",
      "loc": ["submission", "invention_title"],
      "msg": "Field 'invention_title' is required when source_format is 'ST26'"
    },
    {
      "type": "format_forbidden_field_present",
      "loc": ["submission", "trad_submission_category"],
      "msg": "Field 'trad_submission_category' is not allowed when source_format is 'ST26'",
      "severity": "warning"
    }
  ]
}
```

## Validation 機構の設計

eslint のアーキテクチャを参考にした設計。

**原則: record は純粋な data。validation config は外付け。**

```
record.json          -> pure data (what)
rules (Python)       -> validation logic (check + fix)
config (CLI/API)     -> which rules to run, at what severity (how)
```

### Rule の Python interface

```python
class Rule(Protocol):
    id: str                          # "bp/title-required"
    default_severity: Severity       # error / warning

    def check(self, record, context) -> list[Diagnostic]: ...
    def fix(self, record, diagnostic) -> Record | None: ...  # optional
```

### Rule の構成

```
This repo (ddbj-record-specifications)
├── Rules (individual, Python interface)
│   ├── bp/title-required
│   ├── bp/organism-required
│   ├── bs/attributes-required
│   ├── sra/library-strategy-valid
│   ├── insdc/feature-key-exists
│   └── ...
├── Rule sets (convenience groupings)
│   ├── BP_RULES, BS_RULES, SRA_RULES, INSDC_RULES, ALL_RULES
│   └── BP_SUBMISSION_RULES
└── Rule definitions (YAML data, loaded by Python rules)
    ├── insdc_feature_table.yaml
    ├── bs_packages.yaml
    └── ...
```

### Consumer による自由な組み合わせ

```python
# Python API
from ddbj_record.rules import BP_RULES, BS_RULES
results = validate(record, rules=BP_RULES + BS_RULES, stage="draft")

# CLI
ddbj-record validate --rules bp,bs --stage draft record.json
ddbj-record validate --rules bp,bs --stage draft --fix record.json
```

### rule と config の責務分離

| 責務 | 担当 | 例 |
|------|------|-----|
| rule の定義 | this repo | `bp/title-required`, `insdc/feature-key-exists` |
| rule set の定義 | this repo | `BP_RULES`, `SRA_RULES` |
| どの rule を使うか | consumer (API / CLI / other tools) | `--rules bp,bs` |
| どの stage で検証するか | consumer | `--stage draft` |
| severity の override | consumer | `--severity bp/title-required=warning` |

## Validation の段階的挙動

| stage | 例 | validation の期待 |
|-------|-----|-------------------|
| draft | submitter がローカルで作成 | 緩い（warning 中心） |
| submission | DDBJ に提出 | 厳密（error で reject） |
| curation | DDBJ staff が編集 | 厳密 + 追加ルール |
| accepted | accession 発行済み | 変更制約あり |
| public | 外部公開済み | validation skip or 読み取り専用 |

## Fix の設計

`--fix` で自動修正可能な操作の分類:

| fix の種類 | 例 | 安全性 |
|-----------|-----|--------|
| 正規化 | 日付フォーマット統一、空白 trim | 安全 |
| 導出 | organism → division 自動決定 | やや安全（taxonomy DB 依存） |
| デフォルト補完 | 欠落フィールドにデフォルト値 | 要注意 |
| 構造変換 | v2 → v3 マイグレーション | converter の責務 |
| curation | qualifier value の修正、organism 名の正規化 | 外部リソース依存 |

CLI オプションとして `--fix=safe`（正規化のみ）/ `--fix=all`（全 fix）の安全性レベル指定と、`--dry-run` による diff 表示を想定する。外部リソース（taxonomy DB 等）に依存する fix は `safe` に含めない。

## 形式固有バリデーションルール

`provenance.source_format` の値に基づいてルールセットを選択し、適用する。`source_format` が `None`（未指定）の場合はこの検証をスキップする。

### ルール定義方法

INSDC feature/qualifier の定義で YAML 外部ファイル（`insdc_feature_table.yaml`）を使用しているため、同じパターンを踏襲する。

```yaml
format_rules:
  ST26:
    submission:
      required: [invention_title]
      optional: [applicant_name, inventor_name, application_identification]
      forbidden: [trad_submission_category, seq_prefix, keywords, datatype]
    source:
      optional: [tax_id]

  TradAnnotation:
    submission:
      required: [trad_submission_category]
      optional: [locus_tag_prefix, seq_prefix, keywords, datatype]
      forbidden: [invention_title, applicant_name, inventor_name]
```

### 各モデルへの適用

形式固有の制約は Submission 以外にも存在しうる。同じバリデーションパターンを他モデルにも適用できる。

| モデル | 形式固有の例 |
|---|---|
| Submission | ST.26: `invention_title` 必須 / TradAnnotation: `trad_submission_category` 必須 |
| Source | ST.26: `tax_id` は補助情報として許容 |
| Entry | ST.26: `division` は `"PAT"` 固定 |
| Feature | ST.26: INSDC のサブセット（使用可能な feature/qualifier が制��される） |

forbidden フィールドに値が入っていた場合の severity（error / warning）は consumer の config で指定する。

## BioSample EAV 調査結果

validation rule 実装時の参考データ。

| 指標 | 値 |
|------|-----|
| DDBJ の unique attribute_name 数 | 1,153（ジャンク含む、実質 400-700） |
| NCBI の harmonized attributes | 960 |
| packages 数 | 229 (NCBI) / 228 (DDBJ) |
| 全 packages 共通の core attributes | 8 (sample_name, organism, taxonomy_id, bioproject_id, collection_date, geo_loc_name, sample_title, description) |
| 1 package あたりの最大属性数 | 203 (MIGS.eu.built) |
| 1 package あたりの平均属性��� | ~88 |
| いず���かの package で mandatory な属性数 | 103 |
| 常に optional な属性数 | 765 |

既存の typed 化の試み:

| プロジェクト | 方式 | 説明 |
|-------------|------|------|
| GenSC MIxS | LinkML (YAML) | MIxS v6.1+ の公式仕様。1000+ slots |
| NMDC Schema | LinkML | `Biosample` class を定義。MIxS ベース |
| EBI BioSamples | JSON Schema | チェックリストごとの JSON Schema |
| DDBJ RDF/OWL | OWL ontology | package/attribute を OWL class/property で定義 |

