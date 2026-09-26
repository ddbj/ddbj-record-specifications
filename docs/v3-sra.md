# SRA XML と v3

DRA のメタデータ（SRA XML）を v3 に載せるときの約束。
[#3](https://github.com/ddbj/ddbj-record-specifications/issues/3) で挙げた選択肢のうち A 案（v3 に型付きで載せる）を採り、情報は失わない。稀な要素も含めて全て型付きの場所に置く。
どれをどこに置くかは [v3-sra-mapping.yml](./v3-sra-mapping.yml) に 1 行ずつ書いた。

#3 で「判断が要らないもの」とした次のものも、失わないために型付きで持つことにした。

- `ACTIONS/ACTION` の `ADD` の `@source` / `@schema` と `RELEASE`（→ `submission.sra.actions[]`）
- `CONTACTS/CONTACT`。`@inform_on_status` と `@inform_on_error` は #3 で調べた例では全て同じ値だったが、別の値を書けるので `submitters[].email` 1 つには畳まない（→ `submission.sra.contacts[]`）
- `@center_name`。#3 で調べた例では submission の中で全て同じ値だったが、オブジェクトごとに書けるので各オブジェクトが持つ
- `IDENTIFIERS/SUBMITTER_ID@namespace`（→ 各オブジェクトの `identifiers[]`）

## 範囲

対応表の行は、次の 2 つに現れる要素と属性の全て。

- SRA XSD の 1.5d2 / 1.5e / 1.5e2 / 1.5.7 / 1.5.8 / 1.5.9 / 1.6.0 / 1.6.1（D-way の dracommon が持つ全版）のうち、submission / study / sample / experiment / run / analysis の 6 種類の文書
- D-way の drmdb（`mass.meta_entity`）に保存された、全ての DRA 文書の全ての版（8,239,358 文書、2026-09-25 に集計）

XSD の package / annotation / reference の文書は D-way に保存されていないので、範囲に入れていない。

対応表は [scripts/sra](../scripts/sra/README.md) の 3 つのスクリプトで作り、このページが引く drmdb の数も同じ場所のスクリプトで出した。

保存された文書には、dracommon のどの版の XSD にも無い要素がある。SRA XSD 1.5 より前の登録で使われていたもの（`GAP_DESCRIPTOR`、SOLiD の `COLOR_MATRIX`、`ENTREZ_LINK` など）で、これもかつて SRA XML として受け付けて公開したものなので、同じように型付きで置く。
そうした項目は各モデルの `legacy` にまとめ、XSD にある項目と分けた。
新しい登録がそれらを使っていないことは、validation rule が `legacy` を見れば確かめられる。
ただし次の 3 つは、XSD にある項目と同じ場所に置くので `legacy` の外にあり、rule が別に確かめる。

- RUN の `DATA_BLOCK@name` / `@serial` → `data_blocks[].name` / `.serial`（ANALYSIS の `DATA_BLOCK` の `@name` / `@serial` は今の XSD にもある）
- `ACTION/MODIFY@target` → `submission.sra.actions[].target`（HOLD などの `@target` は今の XSD にもある）
- `ENTREZ_LINK` / `DDBJ_LINK` → `relations[]` の `properties.sra_link_type`

対応表の行のうち XSD に無いものには、drmdb でその要素を含む文書の数を注記した。
一部の版にしかないもの（`POOLING_STRATEGY` は 1.5d2 だけ、など）には、その版を注記した。

保存された文書のうち 7 つは、他と同じようには読めない。

- 1 つは根が `STUDY_SET` で、中に `STUDY` が 1 つある。`*_SET` を外して他と同じに扱う
- 6 つは整形式でない XML。
  - study の 2 つは、末尾に余分な `</STUDY_SET>` があるものと、XML 宣言の前に空白があるもの。どちらも中身は他と同じ形に読める
  - sample の 4 つは `<SAMPLE_ATTRIBUTE>` の開始タグが 1 つ抜けていて、読むと `TAG` と `VALUE` の一部が `SAMPLE` の直下に並ぶ。書き手の意図は明らかなので、それらも `samples[].attributes[]` に写す（対応表では「整形式でない文書を読み直した形」と注記した）

## 失わないもの

「情報を失わない」とは、次のものを v3 から元の SRA XML と同じに復元できること。

- 値を持つ全ての要素と属性の値
- 要素の入れ子と、値を持つ要素の繰り返しの数
- 繰り返す要素の順序

次のものは情報と見なさず、保たない。

- **値を 1 つも持たない要素や属性**: `<PROCESSING/>`、`<LABEL/>`、`notes=""`、空白だけの文字列は、その要素や属性が無いのと同じに扱う。ただし要素の名前が値になるもの（[下](#要素の名前が値になるもの)）は、中身が空でもその名前という値を持つ。`<LIBRARY_LAYOUT><SINGLE/></LIBRARY_LAYOUT>` や `<ACTION><PROTECT/></ACTION>` は空ではない
- **数と真偽値の字面**: `"0.0E0"` と `"0"`、`"1"` と `"true"` は、同じ数・同じ真偽値として持つ
- **XML としての書き方**: 名前空間の接頭辞、属性の並び、空白による整形、コメント
- **`TAG` の違う `*_ATTRIBUTE` どうしの並び**: 属性は名前で引くもので、名前の違う属性の前後に意味は無い。同じ `TAG` を繰り返したものの並びは保つ
- **参照とリンクの並び**: `*_LINKS` の `URL_LINK` / `XREF_LINK`、`ANALYSIS/TARGETS`、`RELATED_STUDIES` は v3 の `relations` になり、その並びは保たない。どれも同じ種類の参照を並べたもので、並びに意味は無い

`int` / `float` / `bool` にした項目は、drmdb に保存された全ての値がその型で読める（読めない値は 1 つも無かった）。対応表を書く `build_mapping.py` が毎回これを確かめる。
`TAG` が空の `*_ATTRIBUTE` は drmdb に 172 あるが、どれも `VALUE` と `UNITS` も空で、値を持たない。`Attribute.name` を必須とすることと食い違わない。

## 写し方の約束

### オブジェクト

| SRA XML | v3 |
|---|---|
| `SUBMISSION` | `submission` |
| `STUDY` | `project` |
| `SAMPLE` | `samples[]` |
| `EXPERIMENT` | `experiments[]` |
| `RUN` | `runs[]` |
| `ANALYSIS` | `analyses[]` |

`*_SET` は同じ種類の要素を並べる入れ物で、v3 では list そのもの。

どのオブジェクトも `accession` / `alias` / `center_name` / `broker_name` / `identifiers` を持つ。
SRA XML はこれらをオブジェクトごとに書けるので、submission の値から導出しない。

SUBMISSION のうち登録の手続きに関わるもの（`CONTACTS`、`ACTIONS`、`@lab_name` など）は、ST.26 の `submission.st26` と同じく `submission.sra` にまとめた。

### オブジェクトの間の参照

参照は `relations` に置く。起点（`source`）は参照を書いたオブジェクトで、次の順に指す。

1. `accession`
2. accession が無ければ `alias`
3. alias もその種類の中で一意でなければ `index`（その種類の list の中の位置、0 始まり）

accession だけでは足りない。保存された版の多くは accession が付く前のもので、`@accession` を持たない（experiment では 3,450,828 のうち少なくとも 1,411,047）。
alias だけでも足りない。1 つの record の中で alias が重なることがある（`tests/fixtures/v3/raw/dra/ERA000005` では 65 の experiment が同じ alias を持ち、D-way 自身の登録でも DRP で 12、DRS で 5 の submission に重なりがある）。

| SRA XML | relation の type |
|---|---|
| `EXPERIMENT/STUDY_REF`、`ANALYSIS/STUDY_REF` | `part_of`（target.db は `project`） |
| `EXPERIMENT/DESIGN/SAMPLE_DESCRIPTOR` | `part_of`（target.db は `sample`） |
| `RUN/EXPERIMENT_REF` | `part_of`（target.db は `experiment`） |
| `ANALYSIS/TARGETS/TARGET` | `derived_from`（target.db は `@sra_object_type` の値を小文字にしたもの。`STUDY` だけは `project`） |
| `STUDY/DESCRIPTOR/RELATED_STUDIES/RELATED_STUDY` | `related_to`（`IS_PRIMARY` は `properties.is_primary` に `"true"` / `"false"`） |

参照の属性は `RelationTarget` に次のように置く。

| SRA XML | RelationTarget |
|---|---|
| `@refname` | `id` |
| `@accession` | `accession` |
| `@refcenter` | `center_name` |
| `IDENTIFIERS` | `identifiers` |

- SRA の参照は `@refname` と `@accession` を同時に書ける。record 内参照の `id` は以前から alias を指しているので、accession は `accession` という別の欄に置き、どちらか一方に寄せない
- 相手がこの record の中にあるかどうかは書かない。STUDY_REF や TARGET は別の submission のオブジェクトを指すことも多い。読む側が accession か (`center_name`, alias) で探す
- `ANALYSIS/TARGETS` の中身は `(TARGET?, IDENTIFIERS?)+`。`IDENTIFIERS` はすぐ前の `TARGET` の `target.identifiers` に入れる。前に `TARGET` が無い `IDENTIFIERS` は、それだけを target に持つ relation にする
- `SAMPLE_DESCRIPTOR` が参照を持たず（属性も `IDENTIFIERS` も無く）`POOL` だけを持つときは、`part_of` の relation を作らない

参照に加えて値の並びを持つものは、そのオブジェクトの中に置く。

- `SAMPLE_DESCRIPTOR/POOL/MEMBER` → `experiments[].pool.members[]`。`sample` が参照。member は `read_labels` という list を持ち、relation の `properties`（`dict[str, str]`）に収まらない
- `REFERENCE_ALIGNMENT/RUN_LABELS/RUN` → `analyses[].reference_alignment.run_labels[]`。`run` が参照。アラインメントの中の read group を run に結ぶ表で、analysis というオブジェクトについての関係ではない（`seq_labels` と同じ形）

experiment の sample を知るには両方を見る。`SAMPLE_DESCRIPTOR` 自身の参照は `relations` にあり、POOL の member は `pool` にある。

### リンク

`*_LINKS/*_LINK` は `relations` に置く。起点はリンクを書いたオブジェクト。

| SRA XML | relation |
|---|---|
| `URL_LINK` | `reference`（`URL` は target.url、`LABEL` は label） |
| `XREF_LINK` | `xref`（`DB` / `ID` は target.db / target.id） |
| `ENTREZ_LINK`、`DDBJ_LINK`（XSD 1.5 より前） | `xref` に `properties.sra_link_type` = `"entrez"` / `"ddbj"` |

`ENTREZ_LINK` と `DDBJ_LINK` には、XML に戻すときに `XREF_LINK` と見分けるための印を付ける。

`REFERENCE_ALIGNMENT/ASSEMBLY/CUSTOM/REFERENCE_SOURCE` の `URL_LINK` / `XREF_LINK` は、relation ではなく `ExternalRef` の値になる。`url` があれば `URL_LINK`、無ければ `XREF_LINK` に戻す。
drmdb にある `REFERENCE_SOURCE/URL_LINK` 287 は全て `URL` も `LABEL` も空なので、この決め方で取り違えるものは無い。

### 識別子

`IDENTIFIERS` の子は `identifiers[]` に 1 つずつ置き、`type` に種類を書く。

| SRA XML | Identifier.type |
|---|---|
| `PRIMARY_ID` | `primary` |
| `SECONDARY_ID` | `secondary` |
| `EXTERNAL_ID` | `external` |
| `SUBMITTER_ID` | `submitter` |
| `UUID` | `uuid` |

`@accession` と `PRIMARY_ID` は両方書けて、違う値でもよい。前者は `accession`、後者は `identifiers` に置く。
D-way の study は、BioProject の番号（PRJDB）を `PRIMARY_ID`（label は `BioProject ID`）と `RELATED_STUDIES` に書く。それぞれ `project.identifiers[]` と `related_to` の relation になる。

### 要素の名前が値になるもの

SRA XML では、選択肢を子要素の名前で表すところがある。v3 ではその名前を値として持つ。
値は要素名のまま持つ。v3 がすでに小文字の語彙を決めている 2 つだけは小文字にする。

| SRA XML | v3 | 値 |
|---|---|---|
| `PLATFORM/<装置の系統>` | `platform.type` | `ILLUMINA` |
| `ACTIONS/ACTION/<種類>` | `submission.sra.actions[].type` | `ADD` |
| `GAP_DESCRIPTOR/GAP/GAP_TYPE/<種類>` | `legacy.gaps[].type` | `PairedEnd` |
| `LIBRARY_LAYOUT/<SINGLE / PAIRED>` | `library.layout` | `paired`（既存の語彙） |
| `ANALYSIS_TYPE/<種類>` | `analysis_type` | `reference_alignment`（既存の語彙） |

`IDENTIFIERS` の子は、[上の表](#識別子)の語に置き換える。

## これまでの v3 から変わるもの

互換性を壊すもの:

- `Run.files` / `Analysis.files` → `data_blocks[].files`。SRA は file を `DATA_BLOCK` でまとめ、block ごとに名前や pool の member を持つ（1 つの run に複数ある）。平らな list ではその区切りが失われる。JGA の DATA も `DATA_BLOCK` を 1 つ持つ形なので、同じ型にした
- `Experiment.targeted_loci`: `list[str]` → `list[TargetedLocus]`。`LOCUS` は名前のほかに `@description` と `PROBE_SET` を持つ
- `PipelineStep.prev_step_index`: `str` → `prev_step_indexes: list[str]`。XSD で `PREV_STEP_INDEX` は繰り返せる

改めた記述:

- 「center_name は submission.submitters の Organization から導出可能なため含めない」→ 各オブジェクトが持つ
- 「anonymized_name は attributes で扱う」→ typed field。attributes に置くと、同じ名前の `SAMPLE_ATTRIBUTE` と見分けられず XML に戻せない

## 決めたこと

### 失わないものの範囲

[失わないもの](#失わないもの)のとおり、値と構造と順序を保ち、値を持たない要素と XML としての字面は保たない。v3 は XML の中身を写すもので、書き方を写すものではない。字面まで保つには、空の要素ごとに有無の印を持ち、数と真偽値を全て文字列にすることになり、v3 の型が XML の書き方を持ち込む。

### 複数の study を持つ submission

study が 1 つなら、今までどおり同じ record の `project` に置く。2 つ以上なら、study をそれぞれ `project` だけを持つ別の record にし、submission の record は `project` を持たない。

- `project` を 1 つのままにでき、BP を含む読む側を変えずに済む
- SUBMISSION、experiment、run、analysis、sample は 1 つの record に留まるので、どれも写し分けない
- どれか 1 つを主な study に選ぶ規則は置かない。元の XML にその区別が無いので、全て同じ扱いにする
- study の record の `submission` には、その submission の `accession`（DRA）と `hold_date` だけを置く。どの submission の study かがデータ自体に残り、`@target` の無い HOLD は study にも効くので、公開保留日も同じに読める
- experiment や analysis から study への参照は、XML に書かれたまま relation に置く（refname は `target.id`、accession は `target.accession`。[オブジェクトの間の参照](#オブジェクトの間の参照)）。相手が別の record にあっても変わらない。読む側は、同じ `submission.accession` を持つ record の中で、accession か（`center_name`、alias）で相手を探す
- どれかの版で study が 2 つ以上になった submission は、全ての版で分ける。版によって形を変えると、履歴の途中で project が record の外へ移る

該当するのは少なくとも次のとおり。どちらの数え方にも漏れがある。

- experiment の `STUDY_REF` に書かれた study の accession（各 experiment の最新版）で数えると、35,944 submission のうち 5 が 2 つの study を指す。study を refname だけで指す 27,669 の experiment はこれに数えていない
- `mass.accession_relation` で submission（DRA）を親に持つ study（DRP）を数えると、そう記録された 385 submission のうち 37 が 2 つ以上を持ち、最大は 59。削除されていない DRP 17,972 の多くは、この親子として記録されていない

### `hold_date` と `actions` の HOLD

`ACTIONS/ACTION/HOLD` は書かれたとおり（順序も）`submission.sra.actions[]` に置き、`@target` が無く `@HoldUntilDate` を持つ HOLD のうち最後のものの日付を、`submission.hold_date` にも写す（ACTIONS は書かれた順に行うので、最後のものが効く）。検証は、`hold_date` がその日付と同じことを確かめる。

- 公開保留日は、DB によらず `hold_date` から読める。ddbj-repository の BP の公開予告は、record の `submission.hold_date` を写した列を見ている。DRA に広げるときも同じ欄を読めばよい
- HOLD を `actions` から除くと、ACTIONS の並びを失う。同じ値を 2 か所に持つのは、そのための代償（GEA の `Public Release Date` は単独の値なので、共通の欄にだけ置く。[v3-gea.md](./v3-gea.md#他の-db-と同じ意味の欄)）
- `@target` の付いた HOLD は、オブジェクトごとの保留なので `actions` にだけ置く
- 日付の無い HOLD と、日付の代わりに期間だけを書いた HOLD（`legacy.hold_for_period`、1,123 文書）は写さない。`hold_date` は日付の欄で、期間から日付を作ると、何を起点にしたかを推し量ることになる

## ddbj-repository の側でやること

canonical JSON（`ddbj-canon/v2`）の版を上げ、登録簿を次のように直す。

- **順序**: 書かれた順に意味がある list を `ordered` として登録する。`samples` / `experiments` / `runs` / `analyses`（relation が `index` で指すので、並べ替えると別のオブジェクトを指すことになる。SRA の sample は alias も重なる。`tests/fixtures/v3/raw/dra/SRA012004` の 2 つの `HS0896`）、run の `processing` / `reads`、`actions`、`basecalls`、`data_blocks` など。BS の sample も同じ扱いになるが、BS の record の sample の並びは作る側（converter、TSV の取り込み）で決まっているので、差分が揺れることは無い
- **同点の順**: `keyed` の list で key が同じ要素は、書かれた順に並べる（今は sha256 で並べ直している。canonical-json.md §3.1）。SRA の `*_ATTRIBUTE` は同じ `TAG` を繰り返してよく、`[name, unit]` が同じ属性の順は保つ必要がある。`attributes` を `ordered` にすると、BS の差分から並べ替えの揺れを除いた §3.3 の効果が無くなるので、`keyed` のまま同点の順だけを保つ
- **relations の key**: `source/db` と `source/id` は v3 の `RelationSource` に無く、常に空になる。key を `[type, label, source/type, source/accession, source/alias, source/index, target/db, target/id, target/accession, target/center_name, target/url]` にし、同点は書かれた順に並べる。canonical-json.md §3.1 の表と `array-modes.yml` の `/relations` の行も食い違っているので、揃える
- **登録簿の古い行**: `/runs/*/files` と `/analyses/*/files` を除き、`data_blocks` の下に置き直す
- **小数**: `proportion`、`legacy.gaps[].mean` / `stdev`、`legacy.quality_scoring[].multiplier` を `floats` に加える
- **文字列**: NFC と空白の畳み込み（§2.2）は BP / BS と同じに SRA にも掛ける。`*_ATTRIBUTE/TAG` の前後の空白も畳まれるが、字面なので失うものは無い

## 選ばなかった案

- **字面まで保つ。** 上のとおり、v3 の型が XML の書き方を持ち込む
- **`projects: list[Project]` にする。** 1 submission = 1 record は保てるが、少なくとも 37 件のために BP を含む全ての読む側が list を扱うことになる
- **study を常に別の record にする。** 形は study の数によらず 1 つになるが、study が 1 つの大多数の submission まで分かれ、BP と同じ「record が自分の project を持つ」形から外れる
- **study ごとに record を分け、experiment や run も study ごとに写し分ける。** SUBMISSION を複数の record に写すことになり、複数の study の experiment が同じ sample を指すと、sample も写すことになる
- **SRA では `hold_date` を使わない。** 公開保留日を読む側が、SRA だけ別の場所を見ることになる
