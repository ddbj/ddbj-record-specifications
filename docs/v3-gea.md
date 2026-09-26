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

GEA のメタデータの正本は、D-way の GEA の DB（`dordb`）の `mass.metadata` にある。IDF、SDRF、ADF を登録ごとに、版ごとに 1 行ずつ持つ。その全ての版と、CIBEX のファイルを数えた（2026-09-26）。

- 1,034 件の experiment の IDF 4,702 版と SDRF 3,313 版（SDRF は計 66,883 行）。1 件あたり最大 15 版
- 248 件のアレイ設計の ADF 862 版。1 件あたり最大 75 版
- 216 件の CIBEX の `.metadata`。`dordb` には無い（CIBEX を指す accession の行があるだけ）ので、a012 の `/usr/local/resources/gea/cibex`（GEA の公開用の写し）から

accession の振られる前の登録（151 件。D-way の画面で作っている途中のもの）は移さないので、数えていない。

公開用の写し（`/usr/local/resources/gea`）は、公開した 768 件の IDF と SDRF を、公開したときの形で書き出したもの。`dordb` の最新版とは限らず、IDF が最新版と同じなのは 353 件で、350 件は空白だけが違い（`Person Affiliation` の空白など）、38 件は 1 つ前の版と同じ（最新版は公開していない直し）、27 件は文言や日付が違う。この文書の初めの版はそこから数えたもので、公開前の登録と過去の版を加えて数え直すと、次のものが新たに現れた。どれも過去の版か、公開用の写しに無い登録（公開前のものと取り下げたもの）にだけある。

- IDF の `Comment[AdditionalFile:x]`、`Comment[Public Release Date]`
- SDRF の見出しの `[` の前の空白、見出しの無い列、MAGE-TAB がそこに置かない列、表でない SDRF

対応表は [scripts/gea](../scripts/gea/README.md) のスクリプトで作った。

## 失わないもの

[v3-sra.md の「失わないもの」](./v3-sra.md#失わないもの)と同じ。値、入れ子、値を持つ項目の繰り返しの数、繰り返しの順序を保ち、値を持たない項目と字面は保たない。

GEA では、それに次を加える。

- **1 つのノードの中で、種類の違う列の並び**: `Comment` が `Technology Type` の前か後か、といった並びは SDRF ごとに違うが、保たない。同じ種類の列（`Characteristics` どうし、`Protocol REF` どうし）の並びは保つ
- **ファイルの文字コード**: Unicode として読む。UTF-8 でないのは CIBEX の 4 件だけで、どれも Windows の cp1252（`±`、`°`、`’`）
  - `dordb` の IDF のうち 64 件の 97 版は、UTF-8 を 2 度符号化した文字化け（`Ã©`、`Â°` など）を含む。直さずに、読めたとおりの文字として持つ。文字化けかどうかは文字列からは決められず、直すのは登録の中身を変えることだから。公開用の写しも同じ文字化けを持つ
- **`Comment[Related study]` の値の並び**: E-GEAD-414 は `NBDC`、`JGA` の順、E-GEAD-623 は逆だが、保たない。どちらも同じ種類の参照を並べたもので、並びに意味は無い。v3 では `relations` になり、その並びは保たない（[v3-sra.md](./v3-sra.md#失わないもの)）

`build_mapping.py` は、次のものを見つけたら対応表を書かずに止まる。どれも数えたファイルには無い。

- SDRF で、同じ名前の列が並ぶところに、空の欄の後に値がある行。v3 の list は空の値を持たないので、値の位置がずれる
- SDRF で、見出しの無い列にある値。何の値かが分からない
- Source Name で始まる表でも、CSV でも IDF でもない SDRF。黙ってファイルのまま持つと、読めるはずの表を読み損ねたことに気付けない
- IDF で、`Public Release Date` と `Comment[Public Release Date]` の両方を持つもの。どちらも `submission.hold_date` の 1 つの値になる
- IDF で、項目の名前の無い行にある値と、`#` で始まるコメントの行
- CIBEX で、列の説明の表の続きなのか、その節の 1 つなのかを決められない塊

## 写し方の約束

### IDF

IDF は 1 行が 1 つの項目で、値が行に沿って並ぶ。

- 同じ組の項目（`Person *`、`Protocol *`、`Experimental Factor *`）は、n 番目の値どうしが n 番目のものを表す。v3 では組ごとに list にし、n 番目の値を n 番目の要素に置く（`Person Last Name` と `Person First Name` → `submission.submitters[].last_name` / `.first_name`）
  - 組の中で値の数は揃っていなくてよい。`Person Affiliation` は 4,702 版の IDF の全てで 1 つだけで、1 人目の `organizations[0].name` に入る
  - PubMed ID と DOI の両方を持つ IDF は 2 件（E-GEAD-592、1086）の 6 版で、どれも 1 つずつなので、組み合わせに迷うものは無い
- 人は v3 の `Person`、論文は `Publication` を使う
- 他の DB と同じ意味の項目は、他の DB と同じ欄に置く（[下](#他の-db-と同じ意味の欄)）
- GEA が `Comment[...]` に書く項目は、全て型付きの欄にした（`experiment_type`、`channel_type` など）。CIBEX から移した experiment にしかない `Comment[CIBEX *]` は `investigation.legacy` に置く。対応表に無い `Comment[...]` が現れたら、`build_mapping.py` は止まる
- 他のオブジェクトへの参照は `relations` に置く。起点は `{"type": "investigation", "accession": E-GEAD}`
  - `Comment[BioProject]` → `part_of`（target.db は `bioproject`）。experiment が BioProject の一部であることを表す。なお v3 の文書と fixture では、BioSample から BioProject への参照に `part_of` と `child_of` の両方が使われていて、揃っていない
  - `Comment[Related study]` → `related_to`。値は `NBDC:hum0600`、`JGA:JGAS000942` のような「DB:番号」なので、`:` の前を target.db、後を target.id にする
- `Comment[SecondaryAccession]`（CIBEX の CBX）→ `investigation.identifiers[]` の `secondary`
- `Comment[AdditionalFile:x]` → `investigation.additional_files[]`（`type` は x、`name` は値）。SDRF の外のファイル（バーコードと試料の対応表など）を挙げるもの
- 58 件の experiment の IDF（232 版）は、値の中の引用符を MAGE-TAB の `""` でなく `\"` と書いている。これも引用符として読む。引用符が何重にも付いた値（書き出しと読み込みを繰り返したものと見られる）も、値のまま持つ。4 版の SDRF も `\"` を書き、うち 2 版（E-GEAD-693、1075 の v3）は引用符の外の値の末尾にある（`CLEA Japan, Inc.\"`）。これも `"` として読む。引用符の前以外の `\` は、そのまま値の一部として読む（E-GEAD-1205、1227 の v1 の IDF は TeX の `$\mu$` を書いている）

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
| データファイルの列の後の、上のどれでもない列（`Characteristics[x]`、`Parameter Value[x]` など） | `misplaced_columns[]`（`name` は列の見出し、`value` はその行の値） |

- `Comment[x]` は直前のノードのものとして持つ。シーケンスの GEA では、Extract に `LIBRARY_*` が、Assay に `SRA_EXPERIMENT` / `SRA_RUN` が付き、`Array Data File` に DRA の run の accession が入る
  - MAGE-TAB では、`Array Design REF` のすぐ後の `Comment[Array Design REF md5]`（E-GEAD-369）はアレイ設計への参照についてのものだが、これも Assay の `comments[]` に入る。どの列の後にあったかは、種類の違う列の並びとして保たない
- ノードを行の間で共有しない。MAGE-TAB では同じ列の同じ名前は同じノードだが、同じ名前のノードが行ごとに違う値を持つ SDRF がある（Source Name で E-GEAD-414 など 9 件、Extract Name で E-GEAD-648 など 9 件。Labeled Extract とデータファイルにもある）。どれも登録者が名前を使い回したもので、例えば E-GEAD-414 の Source `PDAC3` は、行によって `sample_name` が `PDAC3_Scr`、`PDAC3_MNX1KD`、`PDAC3_HNF1BKD` になる
- 335 行は、末尾の Factor Value（と Unit）の欄が欠けていて、列の数が見出しと合わない。欠けているのは行の末尾の欄だけで、空の欄として読むので、失うものは無い
- 見出しの `[` の前の空白は数えない。`Comment [x]`、`Factor Value [x]`、`Unit [x]` は `Comment[x]` などと同じ（MAGE-TAB の見出しは空白を区別しない）。字面なので保たない
- 見出しの無い列（6 版。E-GEAD-1066 の v1 など）は読まない。どれも値が無い
- MAGE-TAB がそこに置かない列は、行の `misplaced_columns[]` に見出しごと置く（[下](#mage-tab-がそこに置かない列は見出しごと)）
- Source Name で始まるタブ区切りの表でない SDRF は、表として読まず、ファイルのまま `investigation.legacy.unread_sdrf` で指す（[下](#表でない-sdrf-はファイルのまま)）

### ADF（アレイ設計）

248 件の ADF は、形が 3 つに分かれる（1 件は版によって形が変わるので、計は 249 件）。

| 形 | 件数 | 内容 |
|---|---|---|
| MAGE-TAB の ADF | 20 | 見出しの行（`Array Design Name`、`Provider` など）、`[main]`、プローブの表 |
| 装置メーカーの表 | 180 | `Comment[GEAAccession]` の 1 行と、メーカーごとの形のプローブの表（Agilent の `FeatureNum`、GAL の `Block` / `Column` / `Row` など） |
| 中身の無いもの | 49 | `Comment[GEAAccession]` と「This is a dummy array design file.」など |

`Comment[GEAAccession]` の行は、登録者が送ったファイル（v1）には無く、accession を振った後の版で足されている（248 件のうち 247 件の v1 と、2 件の v2 には無い）。

見出しの行は `array_design` の型付きの欄に置く。プローブの表はファイルのまま `array_design.file` で指す。表の列はメーカーごとに違い、行数は中央値で 1 万 2 千、最大で 400 万を超える。DRA のリードファイルと同じく、record には表を写さない。見出しの欄はファイルの見出しから読んだもので、正本はファイル。

### CIBEX

CIBEX の登録は GEA の experiment に移されていて、E-GEAD の `Comment[SecondaryAccession]` が CBX を指す。最新版で CBX を指す E-GEAD は 256 件、指される CBX は 254 件で、2 件（CBX4、CBX6）はそれぞれ 2 件の E-GEAD から指されている。過去の版には、別の E-GEAD の CBX を指し、後の版で直したものがある（E-GEAD-777、779 が CBX223 を指していたなど）。CBX のファイルがあるのは 216 件で、残りの 38 件は写しに無い。

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

- 試料と experiment そのものは BioSample と DRA にあり、SDRF はそれを `Comment[BioSample]` や `Comment[SRA_EXPERIMENT]` / `Comment[SRA_RUN]` で指している。SDRF の Source の `Characteristics[x]` や、シーケンスの GEA（1,034 件のうち 593 件）の Extract の `Comment[LIBRARY_*]` / `INSTRUMENT_MODEL` は、その写し。`samples` / `experiments` に写すと、BioSample と DRA の record と並ぶ 2 つ目の写しができ、どちらが正しいかを決めることになる
- 試料や実験を DB をまたいで探すときは、SDRF が指す BioSample と DRA の record を見る
- ノードの値を行ごとに繰り返す（E-GEAD-648 は 78 行全てが同じ Extract を通る）のは、SDRF を失わずに戻すための代償として受け入れる

IDF を v3 の `project` に写さないのは、IDF が研究（project）ではなく 1 つの実験の記述だから。その実験が属する研究は、`Comment[BioProject]`（IDF の全ての版にある）が指す BioProject にある。

### ADF のプローブの表はファイルのまま

表の列はメーカーごとに違い、MAGE-TAB の ADF（20 件）でも 1 件で最大 400 万行（3 件は 60 万行を超える）ある。表は ADF のファイルのまま `array_design.file` で指し、record には入れない。プローブを record から探すことはできないが、そうする使い道は今は無い。

### MAGE-TAB がそこに置かない列は見出しごと

MAGE-TAB のデータファイルの列（`Array Data File` など）が持つのは `Comment[x]` だけだが、過去の版には、その後に `Characteristics[x]`、`Parameter Value[x]` と `Unit[y]`、`Replicate` が書かれたものがある（E-GEAD-460、492、639、641、889 の 10 版）。どれも後の版で `Factor Value[x]` に直されるか、消されている。

これらは `investigation.sdrf[].misplaced_columns[]` に、列の見出しと値の組として、見出しの並びのまま置く。`Unit[y]` の列も見出しごと 1 つの組にし、`Attribute` の `unit` は使わない（前の列の `unit` にすると y を失う）。これらの列は Factor Value の列の間に書かれていることもあるが（E-GEAD-492、889）、`factor_values[]` との間の並びは、種類の違う列の並びとして保たない（[失わないもの](#失わないもの)）。後の版での直し方に合わせて Factor Value と読み替えることはしない。その版を後の版の目で読むことになり、直したという履歴が消える。`Characteristics` を Source のもの、`Parameter Value` を直前の Protocol REF のものと読むことも、どのノードのものかを書いた人に代わって決めることになるので、しない。

新しい登録は MAGE-TAB の検証を通るので、この欄は移した過去の版にだけ現れる。

### 表でない SDRF はファイルのまま

過去の版には、SDRF として保存されていても、Source Name で始まるタブ区切りの表ではないものが 5 版ある（E-GEAD-670、856 の v1 は CSV、1293 の v1 は R が見出しを書き換えた CSV、324 の v3 と 342 の v2 は IDF）。R が書き換えた見出しは `Source.Name`、`Protocol.REF.1` のようなもの。どれも次の版で表に直されている。

これらは表として読まず、ADF の表と同じくファイルのまま `investigation.legacy.unread_sdrf` で指す。その版の record は `investigation.sdrf` を持たない。文字列として record に入れないのは、canonical JSON が文字列の中の空白をまとめ（canonical-json.md §2.2）、タブで区切った欄の境目と空の欄が消えるから。

### 他の DB と同じ意味の欄

IDF と ADF の項目のうち、v3 が他の DB でも持つ欄と同じ意味のものは、その欄にだけ置く。IDF や ADF に戻すときは、そこから読む。

experiment（E-GEAD）とアレイ設計（A-GEAD）は別の record で、1 つの record が `investigation` と `array_design` の両方を持つことは無い。

- `Public Release Date`（IDF）と `Comment[Public Release Date]`（ADF、16 件）→ `submission.hold_date`。過去の版の IDF（15 件の 37 版）は `Comment[Public Release Date]` と書き、`Public Release Date` と同じ版にあることは無い。BP の `Hold/@release_date` と同じく、共通の欄にだけ置く。ADF の見出しの欄は file から読んだもので正本は file だが（[ADF](#adfアレイ設計)）、公開保留日は登録の後から変えるもので、`submission.hold_date` が正。ADF の file は受け取ったときのまま
- `Person *` → `submission.submitters[]`。v3 の `submitters` はその登録に関わる人の list で、それぞれが何の役かは `role` で表す（`[0]` が連絡先）。IDF の Person も、その実験の連絡先を役割付きで並べたもの。役割（`Person Roles`）は書かれたとおり `role` に置き、書かれていない人（114 件の 226 版、E-GEAD-338 は 4 人に役割 1 つ）は `role` を空のままにして、推し量って埋めない。書かれた役割は全て `submitter`（7,317）
- `Comment[Last Update Date]` は archive の更新日で、IDF の 1,117 版にある。v3 は archive 管理の日付を record に入れない（[v3-schema.md](./v3-schema.md) の Date）が、移した record では失わないために `investigation.legacy.last_update_date` に書かれたまま持つ。新しい登録には無い。更新日時は ddbj-repository が持つ

## ddbj-repository の側でやること

[v3-sra.md](./v3-sra.md#ddbj-repository-の側でやること)と同じ canonical JSON の版上げで、GEA の次の list を `ordered` として登録する。

- `investigation.sdrf`、その中の `protocol_refs`、`data_files`、`characteristics`、`comments`、`factor_values`、`misplaced_columns`
- `investigation.additional_files`
- `investigation.protocols`、`experimental_designs`、`experimental_factors`、`publications`
- `array_design.term_sources`
- CIBEX の各 list

SDRF の `Characteristics` や `Comment` は表の列で、名前の違う列どうしの並びも保つ（[失わないもの](#失わないもの)）。SRA の `*_ATTRIBUTE` と違い、SDRF の列はファイル全体で共有する見出しで、その並びが表の形そのものだから。名前で並べ替える `keyed` ではなく、`ordered` にする。IDF の `Protocol *`、`Experimental Factor *`、`PubMed ID` / `Publication DOI` も、n 番目の値どうしが組になる並びなので `ordered` にする（BP の `/project/publications` が `keyed` なのとは違う）。`ordered` は空の要素を受け付けない（canonical-json.md §2.5）ので、上の「空の欄の後に値がある行」を止めるのは、この点でも要る。

移すときは、`dordb` の版を record の版に組み直す。experiment の IDF と SDRF は別々に版を重ねる（IDF のほうが版の多いものが 749 件、同じものが 238 件、SDRF のほうが多いものが 47 件）。`update_date` の順に並べ（`export_dordb.rb` の `versions.tsv`）、どちらかの版が変わるごとに、その時点の IDF と SDRF から record の版を 1 つ作る。アレイ設計は ADF の版がそのまま record の版になる。`investigation.legacy.unread_sdrf` と `array_design.file` が指すファイルは、ADF と同じく record の外に置く。

`canon:fields_check` は Ruby の `DDBJRecord::V3` のデータクラスを登録簿（`schema/canon/v3-fields.yml`）と比べる。`investigation` と `array_design` とその下のクラスを Ruby のクラスに足し、登録簿もそれに合わせる。

## 選ばなかった案

- **samples / experiments に写す。** v3 の概念の共通化には沿うが、BioSample と DRA にある試料と実験の 2 つ目の写しになる。SDRF の列と v3 の欄の対応を 1 つずつ決め、書き戻す規則も複雑になる
- **MAGE-TAB の ADF（20 件）の表を型付きで持つ。** 最大 400 万行の表が record に入り、残りの 228 件はファイルのままなので、表の持ち方が 2 通りになる
- **同じ意味の欄を `investigation` にも持ち、共通の欄に写す。** 同じ値が 2 か所にあり、どちらが正しいかを決めることになる。SRA の HOLD は `actions` の並びを失わないために写しを持つが、IDF の項目は単独の値で、共通の欄にだけ置いても失うものが無い
- **CSV の SDRF を CSV として読む。** 見出しがそのまま残っている CSV（E-GEAD-670、856）は表として読めるが、R が見出しを書き換えたもの（E-GEAD-1293）や IDF を取り違えたものは読めない。読み方が 2 通りになり、どれも次の版で直されているので、読める価値が小さい
- **表でない SDRF や、置き場所の無い列を持つ版を移さない。** 履歴を 1 版ずつ移す（ddbj-repository の SubmissionUpdate）ので、1 つの版を落とすと、その前後の差分が 2 版分の変更になる
- **役割の書かれていない人を submitter と見なす。** IDF の Person は研究の連絡先で、登録した本人とは限らない。書かれていない役割は埋めない

## MetaboBank

MetaboBank も MAGE-TAB で登録される（`tests/fixtures/v3/raw/metabobank`）。`investigation` をそのまま使えるかどうかは、同じように全件を数えて確かめる必要がある。
