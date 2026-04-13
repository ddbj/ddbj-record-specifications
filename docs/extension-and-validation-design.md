# スキーマ拡張とバリデーション設計

DDBJ Record に新しいデータ形式（ST.26 等）を追加する際の、スキーマ拡張戦略とバリデーションアーキテクチャの設計を議論する。

## 問題

PR #1 で ST.26（特許配列リスト）形式のフィールドを追加する提案がある。現行の v2 Submission に ST.26 固有の 6 フィールドを加えると、Optional フィールドが増殖する。

```
v2 Submission (11 fields)
+-- common (4): submitters, db_xrefs, references, comments
+-- semi-common (2): hold_date, division
+-- format-specific (5, all Optional):
    +-- TradAnnotation: trad_submission_category, locus_tag_prefix
    +-- WGS: seq_prefix, keywords, datatype

draft Submission (17 fields)
+-- common (4)
+-- semi-common (2)
+-- format-specific (11, all Optional):
    +-- TradAnnotation: trad_submission_category, locus_tag_prefix
    +-- WGS: seq_prefix, keywords, datatype
    +-- ST.26: invention_title, applicant_name, inventor_name,
              application_identification,
              earliest_priority_application_identifications,
              publication_date
```

この問題は Submission に限らない。Source, Entry, Feature も形式ごとに固有フィールドや制約の差異を持ちうる。今後 JGA 等の形式が増えれば、同じ問題が全モデルに波及する。

本ドキュメントでは 2 つの論点を扱う:

1. スキーマ拡張戦略 — 形式固有フィールドをどう構造化するか
2. バリデーション戦略 — 形式固有の制約をどう検証するか

## スキーマ拡張の選択肢

5 つの設計案を検討した。以下では Submission を例にとるが、他モデルにも同じ議論が適用される。

### 案 A: フラット Optional 追加（現 PR の方針）

全フィールドを同一モデルに並べ、形式固有フィールドは `None` を許容する。

```jsonc
// TradAnnotation record
{
  "submission": {
    "submitters": [...],
    "trad_submission_category": "WGS",
    "locus_tag_prefix": "EXAMPLE",
    "invention_title": null,
    "applicant_name": null
  }
}

// ST.26 record
{
  "submission": {
    "submitters": [...],
    "trad_submission_category": null,
    "locus_tag_prefix": null,
    "invention_title": "Method for ...",
    "applicant_name": "National Institute of Genetics"
  }
}
```

- 後方互換性あり（v2.x で追加可能）
- JSON がフラットで扱いやすい（jq, スクリプト）
- 型レベルで「ST.26 なのに `seq_prefix` が入っている」を防げない
- フィールド数が際限なく増える

### 案 B: Discriminated Union

`source_format` で分岐する形式固有 Submission モデルを定義する。

```jsonc
// TradAnnotation record (source_format でモデルが切り替わる)
{
  "submission": {
    "source_format": "TradAnnotation",
    "submitters": [...],
    "trad_submission_category": "WGS"
  }
}

// ST.26 record
{
  "submission": {
    "source_format": "ST26",
    "submitters": [...],
    "invention_title": "Method for ..."
  }
}
```

- 型レベルで形式固有の必須/任意を表現できる
- 破壊的変更（v3 必須）
- Submission 以外にも適用すると組み合わせ爆発が起きる（`TradSubmission` + `ST26Sequences` のような不整合を型で防げない）
- JSON Schema が `oneOf` になり、利用者にとって複雑

### 案 C: 共通部分 + 拡張辞書

共通フィールドだけ型付けし、形式固有は `extensions: dict[str, Any]` に格納する。

```jsonc
{
  "submission": {
    "submitters": [...],
    "extensions": {
      "invention_title": "Method for ...",
      "applicant_name": "National Institute of Genetics"
    }
  }
}
```

- Submission のコアが安定する
- `extensions` 内の型安全性が弱い
- `submitters` を for 文で回しつつ `extensions` 内を参照する、といった二重アクセスが必要

### 案 D: ルートレベル Extension 分離

形式固有情報を各モデルに散らさず、`DdbjRecord` のルートに形式別オブジェクトとして集約する。

```jsonc
{
  "submission": {
    "submitters": [...]
  },
  "st26": {
    "invention_title": "Method for ...",
    "applicant_name": "National Institute of Genetics"
  }
}
```

- コアモデルが安定し、Extension 内で必須/任意を正しく表現できる
- 意味的に近い情報が離れた場所に分散する（`submitters` と `applicant_name` が別オブジェクト）
- 利用者が JSON を処理する際に 2 箇所を参照する必要がある

### 案 E: フラット + バリデーションルール（推奨）

JSON の構造は案 A と同じフラットなまま、形式固有の制約はバリデーション層で担保する。

```jsonc
// TradAnnotation record
{
  "provenance": { "source_format": "TradAnnotation" },
  "submission": {
    "submitters": [...],
    "trad_submission_category": "WGS",
    "locus_tag_prefix": "EXAMPLE",
    "invention_title": null
  }
}

// ST.26 record
{
  "provenance": { "source_format": "ST26" },
  "submission": {
    "submitters": [...],
    "trad_submission_category": null,
    "invention_title": "Method for ...",
    "applicant_name": "National Institute of Genetics"
  }
}
```

バリデーションルールが形式固有の制約を検証する:

```
source_format = "ST26" =>
  required:  invention_title
  optional:  applicant_name, inventor_name, ...
  forbidden: trad_submission_category, seq_prefix, keywords, datatype

source_format = "TradAnnotation" =>
  required:  trad_submission_category
  optional:  locus_tag_prefix, seq_prefix, ...
  forbidden: invention_title, applicant_name, inventor_name, ...
```

詳細は後述の「バリデーション戦略」で述べる。

### 比較

| | JSON の使いやすさ | 型安全性 | 破壊的変更 | 拡張性 | 他モデルへの波及 |
|---|---|---|---|---|---|
| A (flat Optional) | 良い | 低 | なし | 低 | 同じ問題再発 |
| B (Union) | 普通 | 中 | v3 必要 | 中 | 組み合わせ爆発 |
| C (extensions dict) | 普通 | 低 | v3 必要 | 高 | 解決 |
| D (root Extension) | 悪い | 中 | v3 必要 | 高 | 解決 |
| E (flat + validation) | 良い | 低→バリデーションで補完 | なし (v2.x) | 高 | 同パターンで対応可 |

案 E を推奨する理由:

1. 利用者にとってシンプル — JSON がフラットで jq やスクリプトで扱いやすい
2. 後方互換 — v2.x のまま拡張可能で、破壊的変更を回避できる
3. 型だけでは表現できない制約が既に存在する — INSDC feature/qualifier のバリデーションが先行事例

## バリデーション戦略: well-formed と valid の分離

### 基本方針

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
  "schema_version": "v2.4",
  "provenance": {
    "source_format": "ST26"
  },
  "submission": {
    "submitters": [{"name": "Taro Yamada"}],
    "db_xrefs": [],
    "references": [],
    "comments": [],
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

### バリデーションルールの定義

`provenance.source_format` の値に基づいてルールセットを選択し、適用する。`source_format` が `None`（未指定）の場合はこの検証をスキップする。

ルール定義の方法として 2 つの選択肢がある。

#### 方法 1: コード内定義

```python
FORMAT_RULES: dict[str, FormatRule] = {
    "ST26": FormatRule(
        submission=FieldConstraints(
            required=["invention_title"],
            optional=["applicant_name", "inventor_name",
                      "application_identification"],
            forbidden=["trad_submission_category", "seq_prefix",
                       "keywords", "datatype"],
        ),
        source=FieldConstraints(
            optional=["tax_id"],
        ),
    ),
    "TradAnnotation": FormatRule(
        submission=FieldConstraints(
            required=["trad_submission_category"],
            optional=["locus_tag_prefix", "seq_prefix",
                      "keywords", "datatype"],
            forbidden=["invention_title", "applicant_name",
                       "inventor_name", "application_identification"],
        ),
    ),
}
```

- ルールと検証ロジックが近い
- Python の型チェックが効く
- ルール追加にコード変更が必要

#### 方法 2: YAML/JSON 外部ファイル

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

- コード変更なしにルール追加が可能
- 型安全性は YAML 読み込み時の Pydantic パースで担保

INSDC feature/qualifier の定義でも YAML 外部ファイル（`insdc_feature_table.yaml`）を使用しているため、同じパターンを踏襲して方法 2 を推奨する。

### Submission 以外への適用

形式固有の制約は Submission 以外にも存在しうる。同じバリデーションパターンを他モデルにも適用できる。

| モデル | 形式固有の例 |
|---|---|
| Submission | ST.26: `invention_title` 必須 / TradAnnotation: `trad_submission_category` 必須 |
| Source | ST.26: `tax_id` は補助情報として許容 |
| Entry | ST.26: `division` は `"PAT"` 固定 |
| Feature | ST.26: INSDC のサブセット（使用可能な feature/qualifier が制限される） |

## 議論したい点

1. 案 E の採否 — フラット + バリデーションルールの方針で進めてよいか
2. forbidden フィールドの扱い — 他形式用のフィールドに値が入っていた場合、error にするか warning にするか（データ破壊のリスクは低いが、意図しない混在は検出すべき）
3. `source_format` 未指定時の挙動 — 形式固有バリデーションをスキップするか、共通フィールドのみのバリデーションを行うか
4. ルール定義の形式 — コード内定義か YAML 外部ファイルか
5. バージョニング — ST.26 フィールド追加を v2.4 として行うか、バリデーション機能追加と合わせて v3 にするか

## メモ

登録前、登録後、
source format とは、別に、status もある

公開後、公開前
公開後で更に編集が入った場合
実行スキップ
登録者には、この validator を許容する

---

auto curation
--fix option (eslint でいう fix option)
eslint とかの枯れた linter の実装を参考にするのがいいかもしれない

PEP のカテゴリごとの rule とか

---

dfast は、trad 周りかつ登録前 validation っていう単位

---

bioproject / biosample / sra
jga

複数の db をまたがって記述できる

依存関係の metadata

dr_tools の拡充
branch を切って考えてみる？

---

version は、常に後方互換性をもたせる
少なくとも major version 内では

---

gff

converter 相当を dr_tools or

ddbj_record_specifications
ddbj_record_converter

<https://github.com/ddbj/ddbj-record-specifications>

- spec
- validation
- converter の機能も考える

- rest api server にする
- cli
