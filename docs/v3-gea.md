# GEA と v3

GEA（Genomic Expression Archive）のメタデータを v3 に載せるときの約束。
[v3-sra.md](./v3-sra.md) の DRA と同じく、項目は稀なものも含めて全て v3 の型付きの場所に置く。
どれをどこに置くかは [v3-gea-mapping.yml](./v3-gea-mapping.yml) に 1 行ずつ書いた。

GEA のメタデータは 3 種類ある。

| 種類 | accession | 形式 | v3 |
|---|---|---|---|
| experiment | E-GEAD | MAGE-TAB の IDF と SDRF（タブ区切りの表） | `investigation` |
| アレイ設計 | A-GEAD | MAGE-TAB の ADF、または装置メーカーの表 | `array_design` |
| CIBEX の登録 | CBX | GEA の前身 CIBEX の独自形式 | `investigation.legacy.cibex` |

## 範囲

a012 の `/usr/local/resources/gea`（GEA の公開用の写し。`tracesys` が毎日 20:00 に更新する）にある、次の全てのファイル（2026-09-25 に集計）。

- 768 件の experiment の IDF と SDRF（SDRF は計 15,707 行）。livelist にある 770 件のうち、ファイルの無い取り下げ済みの 2 件（E-GEAD-281、317）を除いたもの
- 242 件のアレイ設計の ADF
- 216 件の CIBEX の `.metadata`

公開用の写しなので、次のものは入っていない。

- 公開前の登録。accession は E-GEAD-1310 まで振られているが、livelist にあるのは 770 件（Public 765、Temporarily Suppressed 3、Withdrawn 2）
- 過去の版。写しにはそれぞれの最新版しか無い

これらは D-way の GEA の画面（`dor`）の裏にある API の DB にあると見られ、正本の場所を問い合わせている。読めるようになったら同じスクリプトで数え直し、対応表に足す。

対応表は [scripts/gea](../scripts/gea/README.md) の 2 つのスクリプトで作った。

## 失わないもの

[v3-sra.md の「失わないもの」](./v3-sra.md#失わないもの)と同じ。値、入れ子、値を持つ項目の繰り返しの数、繰り返しの順序を保ち、値を持たない項目と字面は保たない。

GEA では、それに次を加える。

- **1 つのノードの中で、種類の違う列の並び**: `Comment` が `Technology Type` の前か後か、といった並びは SDRF ごとに違うが、保たない。同じ種類の列（`Characteristics` どうし、`Protocol REF` どうし）の並びは保つ
- **ファイルの文字コード**: Unicode として読む。UTF-8 でないのは CIBEX の 4 件だけで、どれも Windows の cp1252（`±`、`°`、`’`）

`build_mapping.py` は、次のものを見つけたら対応表を書かずに止まる。どれも今の写しには無い。

- SDRF で、同じ名前の列が並ぶところに、空の欄の後に値がある行。v3 の list は空の値を持たないので、値の位置がずれる
- CIBEX で、列の説明の表の続きなのか、その節の 1 つなのかを決められない塊

## 写し方の約束

### IDF

IDF は 1 行が 1 つの項目で、値が行に沿って並ぶ。

- 同じ組の項目（`Person *`、`Protocol *`、`Experimental Factor *`）は、n 番目の値どうしが n 番目のものを表す。v3 では組ごとに list にし、n 番目の値を n 番目の要素に置く（`Person Last Name` と `Person First Name` → `persons[].last_name` / `.first_name`）
  - 組の中で値の数は揃っていなくてよい。`Person Affiliation` は 768 件の IDF の全てで 1 つだけで、1 人目の `organizations[0].name` に入る
  - PubMed ID と DOI の両方を持つ IDF は 2 件（E-GEAD-592、1086）で、どちらも 1 つずつなので、組み合わせに迷うものは無い
- 人は v3 の `Person`、論文は `Publication` を使う
- GEA が `Comment[...]` に書く項目は、全て型付きの欄にした（`experiment_type`、`channel_type` など）。CIBEX から移した experiment にしかない `Comment[CIBEX *]` は `investigation.legacy` に置く。対応表に無い `Comment[...]` が現れたら、`build_mapping.py` は止まる
- 他のオブジェクトへの参照は `relations` に置く。起点は `{"type": "investigation", "accession": E-GEAD}`
  - `Comment[BioProject]` → `part_of`（target.db は `bioproject`）。experiment が BioProject の一部であることを表す。なお v3 の文書と fixture では、BioSample から BioProject への参照に `part_of` と `child_of` の両方が使われていて、揃っていない
  - `Comment[Related study]` → `related_to`。値は `NBDC:hum0600`、`JGA:JGAS000942` のような「DB:番号」なので、`:` の前を target.db、後を target.id にする
- `Comment[SecondaryAccession]`（CIBEX の CBX）→ `investigation.identifiers[]` の `secondary`
- 39 件の IDF は、値の中の引用符を MAGE-TAB の `""` でなく `\"` と書いている。これも引用符として読む。引用符が何重にも付いた値（書き出しと読み込みを繰り返したものと見られる）も、値のまま持つ。2 件の SDRF（E-GEAD-693、1075）は、引用符の外の値の末尾に `\"` があり（`CLEA Japan, Inc.\"`）、これも `"` として読む。`\` が引用符の前以外に現れるファイルは IDF と SDRF には無い

### SDRF

SDRF は 1 行が、試料（Source）から protocol を経てデータファイルに至る 1 本の道筋。v3 では 1 行を `investigation.sdrf[]` の 1 つの要素にする。

```
Source → (Protocol REF…) → Extract → (Protocol REF…) → Labeled Extract → (Protocol REF…) → Assay → (Protocol REF…) → データファイル… / Factor Value…
```

| SDRF | v3（`investigation.sdrf[]` の下） |
|---|---|
| `Source Name` と、その後の `Characteristics[x]` / `Comment[x]` | `source.name` / `.characteristics[]` / `.comments[]`（`name` は x） |
| `Extract Name`、`Material Type`、`Comment[x]` | `extract.name` / `.material_type` / `.comments[]` |
| `Labeled Extract Name`、`Label` | `labeled_extract.name` / `.label` |
| `Assay Name`、`Technology Type`、`Array Design REF`、`Comment[x]` | `assay.name` / `.technology_type` / `.array_design_ref` / `.comments[]` |
| `Array Data File` など 4 種のデータファイルの列と、その後の `Comment[x]` | `data_files[]`（`type` は列の名前） |
| `Protocol REF` | 直後のノードの `protocol_refs[]` |
| `Factor Value[x]` と、その後の `Unit[y]` | `factor_values[]`（`name` は x、`unit` は Unit の値、`unit_type` は y） |

- `Comment[x]` は直前のノードのものとして持つ。シーケンスの GEA では、Extract に `LIBRARY_*` が、Assay に `SRA_EXPERIMENT` / `SRA_RUN` が付き、`Array Data File` に DRA の run の accession が入る
  - MAGE-TAB では、`Array Design REF` のすぐ後の `Comment[Array Design REF md5]`（E-GEAD-369）はアレイ設計への参照についてのものだが、これも Assay の `comments[]` に入る。どの列の後にあったかは、種類の違う列の並びとして保たない
- ノードを行の間で共有しない。MAGE-TAB では同じ列の同じ名前は同じノードだが、同じ名前のノードが行ごとに違う値を持つ SDRF がある（Source Name で E-GEAD-414、416、475、666 の 4 件、Extract Name で E-GEAD-648 の 1 件）。どれも登録者が名前を使い回したもので、例えば E-GEAD-414 の Source `PDAC3` は、行によって `sample_name` が `PDAC3_Scr`、`PDAC3_MNX1KD`、`PDAC3_HNF1BKD` になる
- 30 行は、最後の Factor Value の空の欄が欠けていて、列の数が見出しと合わない。欠けているのは空の欄だけなので、失うものは無い

### ADF（アレイ設計）

242 件の ADF は、形が 3 つに分かれる。

| 形 | 件数 | 内容 |
|---|---|---|
| MAGE-TAB の ADF | 18 | 見出しの行（`Array Design Name`、`Provider` など）、`[main]`、プローブの表 |
| 装置メーカーの表 | 175 | `Comment[GEAAccession]` の 1 行と、メーカーごとの形のプローブの表（Agilent の `FeatureNum`、GAL の `Block` / `Column` / `Row` など） |
| 中身の無いもの | 49 | `Comment[GEAAccession]` と「This is a dummy array design file.」など |

見出しの行は `array_design` の型付きの欄に置く。プローブの表はファイルのまま `array_design.file` で指す。表の列はメーカーごとに違い、行数は中央値で 1 万 2 千、最大で 400 万を超える。DRA のリードファイルと同じく、record には表を写さない。見出しの欄はファイルの見出しから読んだもので、正本はファイル。

### CIBEX

CIBEX の登録は GEA の experiment に移されていて、216 件の CBX はそれぞれ 1 件の E-GEAD の `Comment[SecondaryAccession]` から指されている（1 対 1）。CBX を指す E-GEAD は 254 件あり、残りの 38 件の CBX のファイルは写しに無い。

CIBEX のファイルは、移す前の元の登録として `investigation.legacy.cibex` に置く。形式は MIAME に沿った独自のもの。読み方は次のとおり。

- `節の名前:` の行で節が始まる。節の中は `キー<TAB>値` の行で、空行で区切られた塊が、その節の 1 つずつのもの（`Sample:` の節の塊が 1 つの sample）
- タブの無い行は、上の値の続き（値の中の改行）。値には HTML が混じる（`&deg;`、`<br>`）が、そのまま持つ
- `* data text field:` の節は、データファイルの列の名前と説明の表で、`Field<TAB>Description` の見出しの後に 1 行ずつ並ぶ。直前の array design / hybridization / summary の `data_fields[]` に置く。同じ形のファイルを持つ hybridization が並んでいても、表はその前の 1 つにだけ付く（CBX107 は 9 つの hybridization に表が 1 つ）
- この表の後に、見出しの無いまま hybridization などの塊が続くことがある（CBX27、CBX62 など）。キーが全てその節の項目（`Name`、`File` など MIAME で決まったもの）で、その 1 つを名指すキー（`Name`、array design なら `Array sesign accession`）を持つ塊は、その節のものとして読む。キーがその節の項目と重ならない塊は、空行で途切れた表の続きとして読む（CBX134、CBX157）。どちらとも読める塊（表に `Name` や `Description` という名前の列があり、その前で空行が入ったもの）は、今の写しには無く、現れたら `build_mapping.py` は止まる
- CBX253 の 1 つの Reference は、キーと値をタブでなく空白で分けている（5 行）。`Reference:` の節に限り、行頭がその節のキーと空白なら、キーと値として読む
- `Array design:` の節のキー `Array sesign accession` は綴りを誤っているが、全ての CIBEX がこの綴りなので、そのまま読む

## 決めたこと

### MAGE-TAB の形のまま持つ

GEA は MAGE-TAB の形のまま `investigation` に持ち、SDRF は 1 行ずつ `investigation.sdrf[]` に置く。v3 の `samples` / `experiments` には写さない。

- 試料と experiment そのものは BioSample と DRA にあり、SDRF はそれを `Comment[BioSample]` や `Comment[SRA_EXPERIMENT]` / `Comment[SRA_RUN]` で指している。SDRF の Source の `Characteristics[x]` や Assay の `LIBRARY_*` は、その写し。`samples` / `experiments` に写すと、BioSample と DRA の record と並ぶ 2 つ目の写しができ、どちらが正しいかを決めることになる
- 試料や実験を DB をまたいで探すときは、SDRF が指す BioSample と DRA の record を見る
- ノードの値を行ごとに繰り返す（E-GEAD-648 は 78 行全てが同じ Extract を通る）のは、SDRF を失わずに戻すための代償として受け入れる

IDF を v3 の `project` に写さないのは、E-GEAD が自分の BioProject（`Comment[BioProject]`、全 768 件にある）を別に持つため。

### ADF のプローブの表はファイルのまま

表の列はメーカーごとに違い、MAGE-TAB の ADF（18 件）でも 1 件で最大 400 万行（3 件は 60 万行を超える）ある。表は ADF のファイルのまま `array_design.file` で指し、record には入れない。プローブを record から探すことはできないが、そうする使い道は今は無い。

### 他の DB と同じ意味の欄

IDF に書かれたとおり `investigation` に持ち、他の DB と同じ意味の欄にも写す。2 つが一致することは検証で確かめる。SRA の HOLD と `hold_date` と同じやり方（[v3-sra.md](./v3-sra.md#hold_date-と-actions-の-hold)）。

- `Public Release Date` → `submission.hold_date` にも写す
- `Person *` → `submission.submitters` にも写す。役割（`Person Roles`）が書かれた人は全て `submitter`（1,226）で、IDF の Person は GEA に登録した人の欄なので、役割が書かれていない人（83 件の IDF、E-GEAD-338 は 4 人に役割 1 つ）も含め、全員を写す。役割は `investigation.persons[].role` に書かれたままにする
- `Comment[Last Update Date]` は公開用の写しが書いている archive の日付。移行した record には書かれたまま持ち（失わないため）、ddbj-repository で受ける新しい登録には書かない。更新日時は ddbj-repository が持つ（[v3-schema.md](./v3-schema.md) の Date）

`Comment[Related study]` の値の並び（E-GEAD-414 は `NBDC`、`JGA` の順、E-GEAD-623 は逆）は保たない。どちらも同じ種類の参照で、並びに意味は無い。

## ddbj-repository の側でやること

[v3-sra.md](./v3-sra.md#ddbj-repository-の側でやること)と同じ canonical JSON の版上げで、GEA の次の list を `ordered` として登録する。

- `investigation.sdrf`、その中の `protocol_refs`、`data_files`、`characteristics`、`comments`、`factor_values`
- `investigation.persons`、`protocols`、`experimental_designs`、`experimental_factors`、`publications`
- `array_design.term_sources`
- CIBEX の各 list

`Characteristics` や `Comment` は同じ名前が繰り返されることがあり（E-GEAD-424 の Extract は `Comment[LIBRARY_*]` を 2 回ずつ持つ。E-GEAD-455、458、1085 は同じ名前の Factor Value を持つ）、`[name, unit]` をキーにする `keyed` では順序が決まらない。`ordered` は空の要素を受け付けない（canonical-json.md §2.5）ので、上の「空の欄の後に値がある行」を止めるのは、この点でも要る。

## 選ばなかった案

- **samples / experiments に写す。** v3 の概念の共通化には沿うが、BioSample と DRA にある試料と実験の 2 つ目の写しになる。SDRF の列と v3 の欄の対応を 1 つずつ決め、書き戻す規則も複雑になる
- **MAGE-TAB の ADF（18 件）の表を型付きで持つ。** 最大 400 万行の表が record に入り、残りの 224 件はファイルのままなので、表の持ち方が 2 通りになる
- **同じ意味の欄を、他の DB の欄にだけ置く（`investigation` から除く）。** IDF に戻すときに別の場所から読むことになり、IDF の項目と v3 の欄の対応が崩れる。写しを持って検証で一致を確かめる方が、IDF の形も共通の欄も保てる

