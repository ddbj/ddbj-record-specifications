# Converter 機能仕様

DDBJ Record の v1/v2 スキーマ間の双方向変換仕様を定義する。

## 概要

### 変換パス

| from | to | 動作 |
|---|---|---|
| v1 | v2 | フィールドマッピングによる変換 |
| v2 | v1 | フィールドマッピングによる変換 |
| v1 | v1 | identity (そのまま返す) |
| v2 | v2 | identity (そのまま返す) |

サポート外の組み合わせは `ValueError` を送出する。

### バリデーション

- 変換前に入力データを `from` バージョンのスキーマでバリデーションする
- 変換後に出力データを `to` バージョンのスキーマでバリデーションする
- schema_version のレガシー値はバリデーション時に正規化される
- バリデーションエラー時は `ValueError` を送出する

### データロス時の警告

v2->v1 変換で情報が失われる場合、`warnings.warn(UserWarning)` で警告を出力する。変換自体は失敗させず、ベストエフォートで続行する。

## qualifier 値変換ルール

v1 と v2 では qualifier の値の型が異なる。

### v1 -> v2 (文字列に統一)

- `str` -> `Qualifier(value=str)`
- `bool` -> `"true"` / `"false"` に文字列化
- `list` -> 各要素を `Qualifier` に変換

### v2 -> v1 (元の型に復元)

- `"true"` -> `True` (完全一致、case-sensitive)
- `"false"` -> `False` (完全一致、case-sensitive)
- その他 -> そのまま `str`
- 単一要素 -> スカラー値、複数要素 -> リスト
- `Qualifier.id` は v1 に対応がないため破棄される

## v1 -> v2 変換

### schema_version

`LATEST_MINOR_VERSIONS["v2"]` の値を設定する (現在は `"v2.2"`)。

### provenance

| v2 | v1 ソース |
|---|---|
| `provenance.dfast_version` | `COMMON_META.dfast_version` |

### submission

#### submitters

v1 は「ab_name リスト + 単一の contact 情報」というフラット構造。v2 は各 Person が独立して name/email/organization を持つ構造。

変換ロジック:

1. `SUBMITTER.ab_name` リストから Person リストを生成
2. `SUBMITTER.contact` のフルネームから略称候補を生成し、ab_name リストと照合
3. マッチした場合: その Person に name/email/organization を付与し、**submitters リストの先頭に移動**
4. contact が空でない + マッチ失敗: `abbreviation=None` の ghost Person を**先頭に追加**し、警告を出力
5. contact が空 + ab_name あり: 最初の Person に email/organization を付与（警告なし、既に先頭）
6. contact が空 + ab_name 空: フォールバックとして `abbreviation=None` の Person を生成

略称マッチングはカンマ区切り名 (`"Doe, John"`)、西洋式 (`"John Doe"`)、アジア式 (`"Yamada Taro"` -> 先頭が姓) の 3 パターンに対応する。正規化 (ピリオド・ハイフン・スペース除去 + 小文字化) して比較する。

#### db_xrefs

| v1 | v2 |
|---|---|
| `DBLINK.project` | `{db: "bioproject", id: ...}` |
| `DBLINK.biosample` | `{db: "biosample", id: ...}` |
| `DBLINK.sequence_read_archive[]` | `{db: "insdc.sra", id: ...}` (各要素) |

- `DBLINK` が null なら空リスト
- 空文字の値を持つ Xref は生成しない

#### references

| v1 | v2 | ルール |
|---|---|---|
| `title` | `title` | そのまま |
| `ab_name[]` | `authors[]` | `Person(abbreviation=...)` に変換 |
| `status` | `status` | 小文字化 + スペース->ハイフン (`"In Press"` -> `"in-press"`) |
| `year` | `year` | そのまま |

#### comments

`COMMENT[].line` を `list[list[str]]` にフラット化する。

#### keywords / datatype

| v2 | v1 ソース |
|---|---|
| `keywords` | `COMMON.KEYWORD.keyword` (空リストは `None` に変換) |
| `datatype` | `COMMON.DATATYPE.type` |

#### その他

| v2 | v1 ソース |
|---|---|
| `trad_submission_category` | `COMMON.trad_submission_category` |
| `division` | `COMMON_META.division` |
| `locus_tag_prefix` | `COMMON_META.locus_tag_prefix` |
| `seq_prefix` | `COMMON_META.seq_prefix` |
| `hold_date` | `COMMON.DATE.hold_date` (null なら `None`) |

### experiments

`COMMON.ST_COMMENT` から単一の Experiment を生成する。

| v2 | v1 ソース |
|---|---|
| `id` | `"st_comment_experiment"` (固定) |
| `platform.platform_type` | `ST_COMMENT.sequencing_technology` |
| `experiment_attributes.tagset_id` | `ST_COMMENT.tagset_id` |
| `experiment_attributes.assembly_method` | `ST_COMMENT.assembly_method` |
| `experiment_attributes.coverage` | `ST_COMMENT.coverage` (存在時のみ) |
| `experiment_attributes.genome_coverage` | `ST_COMMENT.genome_coverage` (存在時のみ) |

### sequences

#### common_source

`COMMON_SOURCE` の `organism`, `mol_type` をそのまま設定。それ以外のフィールドは qualifier として変換する。

#### entries

各 v1 Entry をそのまま v2 Entry に変換する (id, name, type, topology, sequence)。

**source_features**: v1 の `type == "source"` feature を `SourceFeature` に変換する。qualifier に organism と mol_type が両方ある場合のみ Source を生成する。`ff_definition` は `definition` フィールドに移動する。

**comments**: v1 の `type == "COMMENT"` feature を `comments` に集約する。

### features

v1 の各 entry 内で `type != "source"` かつ `type != "COMMENT"` の feature を v2 のトップレベル `features[]` に変換する。`sequence_id` には所属する entry の ID を設定する。

v2 の `features[]` には COMMENT feature を含めない。コメントは `entries[].comments` に集約する。

## v2 -> v1 変換

### schema_version

`LATEST_MINOR_VERSIONS["v1"]` の値を設定する (現在は `"v1.0"`)。

### DBLINK

| v2 Xref.db | v1 |
|---|---|
| `bioproject` | `DBLINK.project` |
| `biosample` | `DBLINK.biosample` |
| `insdc.sra` | `DBLINK.sequence_read_archive[]` |

上記 3 種以外の db 名は無視される (データロス、警告出力)。

### SUBMITTER

`submitters[0]` を contact person として使用し、フラット構造に変換する。

| v1 | v2 ソース |
|---|---|
| `ab_name` | 全 submitters の abbreviation (null 除外) |
| `contact` | contact person の name |
| `email` | contact person の email |
| `institute` | contact person の最初の institution の name |
| `consrtm` | contact person の最初の consortium の name |
| `country`, `state`, `city`, `street`, `zip` | institution の address |

2 人目以降の submitter の organization 情報は無視される (データロス)。

### REFERENCE

| v2 | v1 | ルール |
|---|---|---|
| `title` | `title` | そのまま |
| `authors[].abbreviation` | `ab_name[]` | null 除外 |
| `status` | `status` | ハイフン->スペース + Title Case (`"in-press"` -> `"In Press"`) |
| `year` | `year` | そのまま |

v2 Reference の journal, volume, doi, pubmed_id, consortiums 等は無視される (データロス)。

### ST_COMMENT

`experiments` から `id == "st_comment_experiment"` の Experiment を探して変換する。それ以外の experiment は無視される (データロス)。

### KEYWORD / DATATYPE

| v2 | v1 |
|---|---|
| `keywords` | `KEYWORD(keyword=...)` (None/空は `KEYWORD = None`) |
| `datatype` | `DATATYPE(type=...)` (None は `DATATYPE = None`) |

### その他

- **COMMENT**: `submission.comments` を `Comment(line=...)` のリストに変換
- **DATE**: `submission.hold_date` があれば `Date(hold_date=...)` を生成
- **trad_submission_category**: `None` または `"WGS"`/`"GNM"` 以外の値の場合はデフォルト `"GNM"` (警告出力)
- **COMMON_META.division**: `None` の場合はデフォルト `"BCT"` (警告出力)

### ENTRIES

1. v2 の `features[]` を `sequence_id` でグルーピング
2. 各 entry に source features -> annotation features -> COMMENT features の順で配置
3. COMMENT feature: `type="COMMENT"` (大文字), `id="{entry_id}_comment_{index}"`

## データロスの整理

### v1 -> v2

なし。v1 の全フィールドは v2 に対応先がある。

### v2 -> v1

| v2 フィールド | 理由 |
|---|---|
| db_xrefs (bioproject/biosample/insdc.sra 以外) | v1 DBLINK がこの 3 種のみ |
| references の journal, volume, doi, pubmed_id 等 | v1 Reference に対応なし |
| references の consortiums | v1 Reference に対応なし |
| authors の name, email, orcid, organization | v1 は abbreviation のみ |
| submitters の orcid | v1 に対応なし |
| 2 人目以降の submitter の organization | v1 は単一 organization |
| id != "st_comment_experiment" の experiments | v1 に対応構造なし |
| experiments の title, design | v1 ST_COMMENT に対応なし |
| provenance (dfast_version 以外) | v1 COMMON_META に対応なし |
| qualifier の id | v1 qualifier は値のリストのみ |

### ラウンドトリップ

**v1 -> v2 -> v1**: 元のデータと一致することを保証する (テストで検証)。ただし contact のフルネームが ab_name とマッチしなかった場合の差異はある。ab_name のメンバーは保持されるが、**順序は変わる場合がある**（contact person が先頭に移動するため）。KEYWORD/DATATYPE も保持される。

**v2 -> v1 -> v2**: データロスにより元に戻らない場合がある。一致は保証しない。

## CLI (`ddbj_record_converter`)

### 引数

| 引数 | 必須 | 説明 |
|---|---|---|
| `--from` | Yes | 変換元スキーマバージョン |
| `--to` | Yes | 変換先スキーマバージョン |
| `-i`, `--input` | Yes | 入力 JSON ファイルパス |
| `-o`, `--output` | Yes | 出力 JSON ファイルパス |

`--from`, `--to` は major version (`v1`, `v2`) に加え、minor version 付き (`v1.0`, `v2.0`) も受け付ける。minor version 付きの場合は major version に正規化される (例: `v2.0` -> `v2`)。

### 処理フロー

```
read JSON -> validate(from) -> convert -> validate(to) -> write JSON
```

### exit code

| ケース | exit code |
|---|---|
| 変換成功 | 0 |
| バリデーションエラー (入力/出力) | 1 |
| JSON パースエラー | 1 |
| 引数エラー (不正バージョン、ファイル不存在) | 2 |
| その他の例外 | 1 |
