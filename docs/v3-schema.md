# v3 の設計方針

v3 は、DDBJ の登録データを 1 つのモデルで扱う major である。

- 対応している形式: Trad (GNM / WGS / MAG / SAG / haplotype)、BioProject、BioSample、SRA / DRA、JGA / AGD、ST.26、GFF、Assembly、GEA
- まだ対応していない形式: MetaboBank、JVar
- v2 以前との後方互換は持たない (v1 / v2 は [v1-v2.md](./v1-v2.md))

型の定義と各フィールドの意味は [`ddbj_record/schema/v3.py`](../ddbj_record/schema/v3.py) にある。ここには、型からは読み取れない設計の方針を書く。

## モデルのまとめ方

DB ごとにモデルを分けず、同じ意味のものを 1 つのモデルにまとめる。

| v3 のキー | まとめたもの |
|---|---|
| `projects` | BioProject、SRA の study、JGA の study、GEA の experiment (IDF) |
| `samples` | BioSample、SRA の sample、JGA の sample、GEA の SDRF の Source |
| `experiments` | SRA の experiment、JGA の experiment、GEA の SDRF の Assay |
| `runs` | SRA の run、JGA の data、GEA の SDRF の生データのファイル |
| `analyses` | SRA の analysis、JGA の analysis、GEA の SDRF の処理済みデータのファイル |
| `sequences` / `features` | Trad と ST.26 の配列と feature table |
| `assembly` | Assembly |
| `array_design` | GEA のアレイ設計 (A-GEAD) |
| `datasets` / `access_control` | JGA の dataset、policy、DAC |
| `submission` | 登録の手続きについての情報 (登録者、公開予定日 (`hold_date`)、SRA の submission、GEA の IDF の Comment など、ST.26 の出願情報) |

- GFF は record の要素にせず、入力の形式として扱う。GFF の feature は `features` に入れる
- 染色体やプラスミドを表すモデルは作らない。`sequences.entries[]` の `name` / `type` / `topology` で表す (例: `{"name": "pPLH-1", "type": "plasmid", "topology": "circular"}`)
- `array_design` は accession を持つ独立した登録で、多くの experiment から参照されるので、`assembly` と同じくトップレベルに置く
- 公開予定日は、どの DB から変換した record でも `submission.hold_date` に置く。SRA の `@target` の無い HOLD の日付も `hold_date` に写し、ACTION 自体は往復のために `submission.sra.actions[]` にそのまま残す。2 つが食い違っていないかは ddbj-validator のルールで確かめる
- GEA の SDRF の Extract と Labeled Extract は、Assay に入る材料として `experiments[].pool.members[]` に置く。Assay に入る Labeled Extract (無ければ Extract) 1 つが member 1 つで、dual-channel の Assay は member を 2 つ持つ。channel ごとに Source や Factor Value が違うことがあるので、Factor Value も member に置く

record 全体にかかる形式固有の情報は、形式ごとのフィールドにまとめる (`submission.st26`、`submission.sra`、`submission.gea`、`provenance.gff`)。1 つのオブジェクトにかかる値は、そのモデルのフィールドに置く (GFF の `score`、SRA の `center_name`、MAGE-TAB の `protocol_refs` など)。MAGE-TAB の `Comment[x]` は、v3 に同じ意味のフィールドがあるもの (`Comment[BioSample]` など) を除き、そのノードの `comments` に名前と値で置く。

SRA XSD 1.5 より前の要素のように、形式の古い version にしか無い要素は、そのモデルの `legacy` に置く。GEA の前身の CIBEX の登録は `submission.gea.legacy` に置く。新しい登録が `legacy` を使っていないかは、ddbj-validator のルールで確かめる。

## 型が保証する範囲

v3 の型が保証するのは、JSON として読めて型に合うこと (well-formed) までである。「BioProject として登録できるか」のような、登録データとしての正しさ (valid) は ddbj-validator のルールが判定する。

- 全てのフィールドを optional (`T | None`) にし、どの形式から変換した record も読めるようにする。例外は `Attribute.name` で、名前の無い属性は何の値か分からないので必須にしている
- 「何の record か」を示すフィールド (record_type のようなもの) は持たない。何として正しいかは、どのルールを通るかで決まる。変換元の形式と分類 (WGS / GNM など) は `provenance` に置く
- 選択肢のある値も `str` にし、許す値はルールで決める ([versioning.md](./versioning.md))
- 登録者が書く値は、数に見えても `str` にする。例えば `organism.taxonomy_id` は、元の形式では文字列で、`"009606"`、空、`"not applicable"` も書かれる。数にすると record として読めなくなり、ルールがそれを指摘できない。数や真偽値の型にするのは、元の形式 (SRA XSD、GFF など) が数と決めていて、保存されている値がどれも数として読めるものだけ
- BioSample の属性は約 960 種あり、全てを型付きのフィールドにはしない。型付きのフィールドがあるものはそこに置き、残りを `attributes` (name / value / unit) に置く。必須かどうかはルールで決める

例えば次の record は v3 の型で読める。ST.26 として必須の出願情報 (`submission.st26`) が無いことは、ddbj-validator のルールが指摘する。

```json
{
  "schema_version": "v3",
  "provenance": {"source_format": "ST.26 XML"},
  "submission": {"submitters": [{"name": "Taro Yamada"}]}
}
```

## 元の形式との往復

SRA XML、GEA のメタデータ、ST.26 の配列表のヘッダーから変換した record は、元の形式に戻せる。ddbj-repository は record の形で保存し、公開用の XML などをそこから作るためである。

- 戻せるのは、値、入れ子、繰り返しの数、繰り返しの順序
- 保たないのは、値を持たない要素、数の書き方、XML の書式 (属性の並び、空白、コメント)。例えば `NOMINAL_SDEV="0.0E0"` は `nominal_sdev: 0.0` になり、`0.0E0` には戻らない
- 日付は ISO 8601 に書き直し、戻すときは元の形式の書き方にする (ST.26 の Bibliography の `20241203` など)。決まった書き方でない日付は、書かれたまま持って書かれたまま戻す
- 大きな表 (アレイ設計のプローブの表など) とリードファイルは record に入れず、`File` で指す
- GEA の SDRF の行は record に持たず、オブジェクトと relations から作り直す。行の順序と、全く同じ行の繰り返しは保たない。作り直し方は GEA の対応表 (`gea.yml`) の冒頭にある

形式の要素を v3 のどこに置くかは、[`tests/fixtures/v3/mapping/`](../tests/fixtures/v3/mapping/) の対応表に 1 行ずつ書いてある。変換そのものは利用側が行う。対応表をどう確かめているかは [tests/README.md](../tests/README.md) にある。

## record に入れないもの

- 公開状態 (status) と、登録システムが管理する日付 (作成日・更新日・公開日) は record に入れず、登録システムの側で持つ
- ただし、元の形式に書かれている日付は、往復のためにそのまま持つ (GEA の IDF の `Comment[Last Update Date]` など)
- 日付は ISO 8601 で書き、精度の違いを許す (`"2024-01-15"`、`"2024-01"`、`"2024"`)

## 1 つの record の範囲

- `projects` と `samples` のように、複数の DB の情報を 1 つの record に入れてよい。登録の途中で accession を書き足しながら、同じ record を更新していく使い方を想定している
- 1 つの登録を 1 つの record のまま持てるように、project も list (`projects`) にする。SRA の submission は study を複数持てて、BioProject XML も project を複数書ける。いくつまで許すかは ddbj-validator のルールで決める
- umbrella の親子関係は `relations` で表す。親と子を同じ record に入れてもよい

## オブジェクトの識別子

record の中で accession と alias を持つもの (`projects[]`、`samples[]`、`runs[]`、`sequences.entries[]` など) を、ここではオブジェクトと呼ぶ。登録前は alias だけを書き、登録後に accession を書き足す。

- accession 以外の識別子 (SRA の SECONDARY_ID など) は `identifiers` に置く
- 元の形式で名前が同じでも値が違うもの (GEA の SDRF の Source など) は、同じ alias の別のオブジェクトにする
- SRA から変換したオブジェクトは `center_name` も持つ。SRA はオブジェクトごとに別の値を書けるので、submission の値から導かない
- Feature と Qualifier は accession を持たず、alias だけで識別する

## オブジェクトの間の関係

オブジェクトの間の関係と、外部への参照は `relations` に置く。SRA の experiment -> sample や run -> experiment のように、元の形式で必ず 1 本ある参照も `relations` に置く。型は全てのフィールドを optional にするので、フィールドにしても「必ずある」は表せず、GEA の run のように複数の experiment に属するものもあるためである。

ただし、参照に別の値が付くものと、値の一部として別のものを指すものは、その場に置く。例えば `experiments[].pool.members[].sample` は、member が割合や label を持つのでその場に置く。ほかに `experiments[].platform.array_design`、`features[].sequence_id`、`features[].parent_ids`、`ExternalRef` を使うフィールドがこれに当たる。

| type | 意味 | 例 |
|---|---|---|
| `reference` | URL への参照 | project のホームページ |
| `xref` | 外部 DB の項目への参照 | PubMed の論文 |
| `part_of` | 起点が相手の一部である | experiment -> sample、run -> experiment、sample -> BioProject |
| `child_of` | 起点が相手の子である | umbrella の子 project -> 親 project |
| `derived_from` | 起点が相手から派生した | BioSample の派生、SRA の analysis の TARGETS、GEA の処理済みデータ -> 元のデータと Assay |
| `related_to` | 起点が相手に関係する | SRA の RELATED_STUDIES |
| `contains` | 起点が相手を含む | JGA の dataset -> run / analysis |
| `governed_by` | 起点が相手の規約に従う | JGA の dataset -> policy |
| `managed_by` | 起点を相手が管理する | JGA の policy -> DAC |

- 起点 (`source`) は record の中のオブジェクトで、`type` にその種類 (`run` など) を書く。`accession` で指し、無ければ `alias` で指す。alias も一意でなければ、list の中の位置 (`index`、0 始まり) で指す。SRA や GEA から変換した record には、accession の無いオブジェクトも、alias が重なるものもある
- `source` を省くと、record 全体が起点になる
- オブジェクトの種類は、record のキーの単数形で書く (`samples` の要素なら `sample`、`analyses` なら `analysis`、`access_control.policy` なら `policy`)。起点の `type` も相手の `db` も同じ名前を使う
- 相手 (`target`) は、`url` か、`db` と `id` で指す。`db` がオブジェクトの種類 (`sample` など) のときは、`id` に alias、`accession` に accession を書く。相手がこの record の中にあり、accession が無く alias も一意でないときは、`index` も書く。それ以外では、相手がこの record の中にあるかどうかは表さない

```json
{
  "runs": [{"accession": "DRR000001", "alias": "run-1"}],
  "relations": [
    {
      "type": "part_of",
      "source": {"type": "run", "accession": "DRR000001"},
      "target": {"db": "experiment", "id": "exp-1", "accession": "DRX000001"}
    }
  ]
}
```
