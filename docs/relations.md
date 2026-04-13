# Relations 実例集

`DdbjRecord.relations` フィールドの具体的な使用例をまとめる。

## 型定義

```python
class RelationSource(BaseModel):
    type: str | None    # "sample", "project", "experiment", "run", "analysis", ...
    alias: str | None   # record 内オブジェクトの alias

class RelationRef(BaseModel):
    db: str | None      # "bioproject", "biosample", "experiment", "sample", ...
    id: str | None      # accession or alias

class Relation(BaseModel):
    type: str | None            # "child_of", "derived_from", "part_of", ...
    source: RelationSource | None  # record 内の起点（省略時は record 全体）
    target: RelationRef | None
    properties: dict[str, str] | None
```

## links との使い分け

| 用途 | 使うフィールド | 例 |
|------|---------------|-----|
| 外部 DB への参照（accession による紐付け） | `links` | BioProject/BioSample accession の参照 |
| URL リンク | `links` | 関連 Web ページへのリンク |
| オブジェクト間の意味的関係 | `relations` | record 内参照、親子関係、派生関係 |

これまでの dbXref -> 外部 DB への参照

## relation type 一覧

| type | 意味 | 主な用途 |
|------|------|---------|
| `part_of` | 起点が対象の一部である | SRA Experiment → Sample, Run → Experiment |
| `child_of` | 起点が対象の子である | Umbrella BioProject の親子関係 |
| `derived_from` | 起点が対象から派生した | BioSample の派生関係（培養株 → 元株） |
| `governed_by` | 起点が対象のポリシーに従う | JGA Dataset → Policy |
| `managed_by` | 起点が対象に管理される | JGA Policy → DAC |
| `contains` | 起点が対象を含む | JGA Dataset → Run/Analysis |

## 実例

### 1. SRA record 内参照（Experiment → Sample, Run → Experiment）

SRA の典型的なオブジェクトグラフ。1 record 内で Experiment が Sample を、Run が Experiment を参照する。

```json
{
  "samples": [
    {"accession": "SAMD00000001", "alias": "sample-1", "title": "Human liver sample"}
  ],
  "experiments": [
    {"accession": "DRX000001", "alias": "exp-1", "title": "RNA-seq experiment"}
  ],
  "runs": [
    {"accession": "DRR000001", "alias": "run-1", "title": "Sequencing run 1"}
  ],
  "relations": [
    {
      "type": "part_of",
      "source": {"type": "experiment", "alias": "exp-1"},
      "target": {"db": "sample", "id": "sample-1"}
    },
    {
      "type": "part_of",
      "source": {"type": "run", "alias": "run-1"},
      "target": {"db": "experiment", "id": "exp-1"}
    }
  ]
}
```

XSD 対応: `EXPERIMENT/SAMPLE_DESCRIPTOR`, `RUN/EXPERIMENT_REF`

### 2. SRA Analysis → Study 参照

Analysis が Study（= Project）を参照するケース。

```json
{
  "project": {"accession": "PRJDB12345", "alias": "my-project"},
  "analyses": [
    {"accession": "DRZ000001", "alias": "analysis-1", "analysis_type": "de_novo_assembly"}
  ],
  "relations": [
    {
      "type": "part_of",
      "source": {"type": "analysis", "alias": "analysis-1"},
      "target": {"db": "bioproject", "id": "PRJDB12345"}
    }
  ]
}
```

XSD 対応: `ANALYSIS/STUDY_REF`

### 3. Umbrella BioProject の親子関係

Umbrella project の子 project を表現する。1 record = 1 project のため、子 project の record から親を参照する。

```json
{
  "project": {
    "accession": "PRJDB99999",
    "title": "Genome sequencing of bacterial strains",
    "project_type": "primary"
  },
  "relations": [
    {
      "type": "child_of",
      "source": {"type": "project", "alias": null},
      "target": {"db": "bioproject", "id": "PRJDB00001"}
    }
  ]
}
```

source を省略して record 全体を起点とする書き方も可能:

```json
{
  "relations": [
    {
      "type": "child_of",
      "target": {"db": "bioproject", "id": "PRJDB00001"}
    }
  ]
}
```

### 4. BioSample の派生関係（derived_from）

培養株や処理後サンプルが元サンプルから派生した関係。

```json
{
  "samples": [
    {"accession": "SAMD00000010", "alias": "derived-sample", "title": "Cultured strain"}
  ],
  "relations": [
    {
      "type": "derived_from",
      "source": {"type": "sample", "alias": "derived-sample"},
      "target": {"db": "biosample", "id": "SAMD00000001"}
    }
  ]
}
```

XSD 対応: BioSample XSD の `Relations/derived_from`

### 5. JGA controlled-access chain（Dataset → Policy → DAC）

JGA 固有のアクセス制御チェーン。Dataset → Policy → DAC の参照関係。

```json
{
  "datasets": [
    {"accession": "JGAD000001", "alias": "dataset-1", "title": "Exome data"}
  ],
  "access_control": {
    "policy": {
      "accession": "JGAP000001",
      "alias": "policy-1",
      "title": "Data access policy"
    },
    "dac": {
      "accession": "JGAC000001",
      "alias": "dac-1"
    }
  },
  "relations": [
    {
      "type": "governed_by",
      "source": {"type": "dataset", "alias": "dataset-1"},
      "target": {"db": "jga.policy", "id": "JGAP000001"}
    },
    {
      "type": "managed_by",
      "source": {"type": "policy", "alias": "policy-1"},
      "target": {"db": "jga.dac", "id": "JGAC000001"}
    },
    {
      "type": "contains",
      "source": {"type": "dataset", "alias": "dataset-1"},
      "target": {"db": "jga.analysis", "id": "JGAR000001"}
    }
  ]
}
```

XSD 対応: `DATASET/POLICY_REF`, `POLICY/DAC_REF`

### 6. 複数 Sample を持つ record 内の個別参照

`samples` に複数のサンプルがある場合、`source` で「どのサンプルからの関係か」を明示する。

```json
{
  "samples": [
    {"alias": "tumor-sample", "title": "Tumor tissue"},
    {"alias": "normal-sample", "title": "Normal tissue"}
  ],
  "experiments": [
    {"alias": "tumor-exp", "title": "Tumor RNA-seq"},
    {"alias": "normal-exp", "title": "Normal RNA-seq"}
  ],
  "relations": [
    {
      "type": "part_of",
      "source": {"type": "experiment", "alias": "tumor-exp"},
      "target": {"db": "sample", "id": "tumor-sample"}
    },
    {
      "type": "part_of",
      "source": {"type": "experiment", "alias": "normal-exp"},
      "target": {"db": "sample", "id": "normal-sample"}
    }
  ]
}
```

### 7. source 省略（record 全体が起点）

source を省略すると、record 全体が関係の起点となる。record が単一の project や sample のみを含む場合に簡潔に書ける。

```json
{
  "project": {"accession": "PRJDB12345", "title": "My project"},
  "relations": [
    {
      "type": "child_of",
      "target": {"db": "bioproject", "id": "PRJDB00001"}
    }
  ]
}
```

### 8. properties 付き relation

追加情報が必要な場合に `properties` を使う。

```json
{
  "relations": [
    {
      "type": "part_of",
      "source": {"type": "sample", "alias": "sample-1"},
      "target": {"db": "bioproject", "id": "PRJDB12345"},
      "properties": {
        "registration_date": "2025-01-15",
        "note": "Added in second batch"
      }
    }
  ]
}
```

## 典型的な登録パターンごとの relations

### BP only（47.0%）

relations は通常不要（project 単体のため）。umbrella の子の場合のみ `child_of` を持つ。

### BP + BS + SRA（33.8%）

```json
{
  "relations": [
    {
      "type": "part_of",
      "source": {"type": "experiment", "alias": "exp-1"},
      "target": {"db": "sample", "id": "sample-1"}
    },
    {
      "type": "part_of",
      "source": {"type": "run", "alias": "run-1"},
      "target": {"db": "experiment", "id": "exp-1"}
    }
  ]
}
```

BioProject/BioSample への accession 参照は `links` で表現する。

### BP + BS + SRA + Trad（6.7%）

SRA の relations に加え、assembly が project を参照する場合がある。features の sequence 参照は `Feature.sequence_id` フィールドで直接表現するため relations は不要。
