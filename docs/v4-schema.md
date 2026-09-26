# v4 の設計方針

v4 は、v3 の record を 1 つの zip（パッケージ）で渡す major である。record の中身は v3 と同じで（[v3-schema.md](./v3-schema.md)）、変わるのは次の 2 つだけ。

- **渡し方**: record を 1 つの JSON にせず、数の限られたもの（submission、projects など）を `record.json` に、数に上限の無いオブジェクトの list（sample、entry、feature など）を list ごとの JSON Lines に、配列を FASTA に置き、1 つの zip にまとめる
- **entry**: 配列を持たず、配列の長さと digest を持つ。配列は FASTA にあり、alias で引く

型は [`ddbj_record/schema/v4.py`](../ddbj_record/schema/v4.py)、パッケージを読み書きするものは [`ddbj_record/package.py`](../ddbj_record/package.py) にある。使い方は [usage.md](./usage.md)。ここには、型からは読み取れない、パッケージの形と約束を書く。

```
genome.ddbj.zip
├── mimetype              application/vnd.ddbj.record+zip（先頭、無圧縮）
├── record.json           submission、projects など（"schema_version": "v4"）
├── sequences/
│   └── entries.fa        配列。見出しは entry の alias
├── entries.jsonl         1 行に 1 entry。長さと digest を持つ
└── features.jsonl        1 行に 1 feature
```

v4 の型は、変わる `Entry` と、それを含む `Sequences`、`DdbjRecord` だけを定義し、ほかは v3 のものを使う。v3 のクラスを継承しないのは、v4 の record を v3 の record として受け付けさせないため。v4 が使う v3 のモデル（`Sample` など）は、v3 で変われば v4 でも同じに変わる。v4 で定義し直した 3 つのモデルは v3 の欄を写しているので、v3 に欄が増えたり型が変わったりしたら、写しも直す（テストが食い違いを見つける）。

## なぜ v3 と分けるか

v3 の record は 1 つの JSON で、ddbj-repository は BioProject と BioSample をその形で持ち、ddbj-validator もその形の record を読む。v4 のパッケージは、配列の無い record でも形が変わる（sample が `samples.jsonl` に移る）ので、v3 を読むもの全てを壊す。v3 の中の変更にせず、新しい major にして（[versioning.md](./versioning.md)）、`pack` / `unpack` で行き来できるようにする。`pack` / `unpack` は v3 と v4 の間の converter に当たるが、JSON の record ではなく zip のパッケージを読み書きし、`check` と同じ約束を使うので、`ddbj_record/converter/` ではなく `ddbj_record/package.py` に置く。

移る間は、次のようにする。

- ddbj-repository は、受け取りで v3 の JSON と v4 のパッケージの両方を受け、v3 の JSON は受け取ったところで `pack` と同じ変換で v4 にする。保存してある record は移し替える
- v3 しか読めないもの（ddbj-validator など）には、`unpack` で v3 に戻して渡す。v4 を読めるようになったら、戻すのをやめる
- 版を決めるのは `record.json` の `schema_version`（`"v4"`。minor は付けない）。MIME type には版を入れない。v4 が知らない JSON Lines（将来の版で増えたもの）は、v4 の `check` では「パッケージのメンバーでない」になる。形を変えるときは版を上げる

## なぜ

record は、2 通りの理由で大きくなる。

- **配列が大きい。** ゲノムの登録（Trad）では、record の大半が配列になる。染色体レベルのゲノムは数 Gbp あり、植物には数十 Gbp のものもある。entry の数は少なく、1 本が大きい
- **オブジェクトが多い。** JPO から受け取った ST.26 の配列表（2 万件あまり、計 20 GB ほど）では、配列は全体の 21% で、最大のもの（1.66 GB、141 万 entry）では 1.8% しかない。大きさは entry と feature の数から来ている。BioSample には 1 件に 10 万 sample のものがある

どちらでも、record を 1 つの JSON にすると次のことが難しくなる。ゲノムはまだ扱ったことが無いが、ST.26 と BioSample では既に起きている。

- **丸ごと読まないと何も分からない。** 何の登録か、entry がいくつあるかを知るだけで、全体を読むことになる。普通の JSON パーサーは全体をメモリに載せ、流して読むには特別な工夫が要る
- **少し直すだけで、全体を書き直すことになる。** 差分も履歴（JSON Patch の連鎖）も、全体の大きさで扱うことになる

配列を FASTA に、オブジェクトを 1 行ずつ JSON Lines に出せば、どちらの理由で大きくても、1 度に読むのは 1 行か FASTA の決まった大きさの塊で済む。

配列を JSON Lines の中に書かないのは、ゲノムでは 1 本の配列が 1 GB を超え、その entry の行が 1 GB の JSON になるため。JSON は 1 行を丸ごと読まないと解釈できないので、大きな JSON の問題が行の単位で戻ってくる。配列を FASTA に分ければ、entry の行は小さく、配列は FASTA のまま流して読め、samtools などの道具もそのまま使える。

## 形

### zip

- ZIP64 を使ってよい（4 GB を超えるファイル、65,535 を超えるメンバー）
- メンバーは `mimetype`、`record.json`、下の JSON Lines、`sequences/` の下の FASTA だけ。ディレクトリ、シンボリックリンクも含め、ほかのものは入れない
- メンバーの名前は、空白の無い印字可能な ASCII で `/` で区切った相対パス。`..`、先頭の `/`、`\`、ドライブ名（`C:`）は使わない。同じ名前を 2 度入れない
- 圧縮は deflate か無圧縮だけ（Deflate64、LZMA などは使わない）。暗号化しない。塩基配列は deflate でおよそ 3 分の 1 になる
- `mimetype` の後のメンバーの順は決めない。読む側は末尾の目次で引く。書く側は `record.json` を `mimetype` のすぐ後に置くとよい（流して読む側が先に読める）。`entries.jsonl` の digest は配列を書き終えてから決まるので、流して書くなら FASTA の後になる
- 大文字小文字だけが違う名前を重ねない（大文字小文字を区別しないファイルシステムに展開すると重なる）
- 拡張子は `.ddbj.zip`。`.zip` で終わるので、普通の道具で開ける

### mimetype

ファイルの先頭のメンバーで、zip の目次でも先頭（ファイルの中の位置が 0）。無圧縮で、extra field と data descriptor を付けない。中身は `application/vnd.ddbj.record+zip` だけ（改行も付けない）。ODF や EPUB と同じく、ファイルの先頭 38 バイトの後に MIME type が続くので、先頭の数十バイトを見れば何かが分かる。Info-ZIP の `zip` で作るなら、mimetype だけを先に入れ、残りを別に足す。`-X` で extra field を、`-D` でディレクトリのメンバーを付けない。

```sh
zip -X -0 x.ddbj.zip mimetype
zip -X -D -r x.ddbj.zip record.json *.jsonl sequences
```

### record.json

v4 の DdbjRecord から、下の JSON Lines に置く list を除いたもの。その list を `record.json` に書いてはいけない（空の list も）。`schema_version` は `v4`。4 MiB まで（GEA の CIBEX を移した record でも 1 MB に届かない）。

### JSON Lines

DdbjRecord の次の list は、list ごとの JSON Lines（1 行に 1 つのオブジェクト）に置く。1 行は、その list の要素のモデル（`Sample`、`Entry` など）に合う JSON のオブジェクト。

| list | ファイル |
|---|---|
| `samples` | `samples.jsonl` |
| `experiments` | `experiments.jsonl` |
| `runs` | `runs.jsonl` |
| `analyses` | `analyses.jsonl` |
| `datasets` | `datasets.jsonl` |
| `sequences.entries` | `entries.jsonl` |
| `features` | `features.jsonl` |
| `relations` | `relations.jsonl` |

- 対象は、数に上限の無いオブジェクトの list。`projects` を除く DdbjRecord のトップレベルの list と、`sequences.entries`。大きくなったときだけ外に出す形にすると、読む側が 2 通りになるので、常に外に出す
- `projects` は `record.json` に残す。1 つの登録の project は、SRA の submission の study でも数十まで（DRA の全ての submission で最大 59）で、submission と並んで最初に読みたいもの
- list が空なら、ファイルを入れない（空のファイルも入れない）。ファイルが無いことと、list が空であることは同じ
- 行の順は list の順で、`n` 行目が list の `n - 1` 番目。relation の `index`（その種類の list の中の位置）は、JSON Lines に置く list ならそのファイルの行を、`projects` なら `record.json` の `projects` の中の位置を指す。空の行を許さないのはこのため
- JSON は I-JSON（RFC 7493）のもの。UTF-8 で書き、BOM を付けない。`NaN`、`Infinity`、倍精度で表せない数（`1e400`、±(2^53 − 1) を超える整数、倍精度で丸めると値の変わる桁を持つ `1.00000000000000000001`）、対になっていないサロゲート（`\ud800`）、同じ key の繰り返しは使わない。倍精度の最も短い表記で書いた数（`0.1`）は使ってよい。改行は LF か CRLF。1 行は 1 MiB まで（配列を FASTA に出すので、1 つのオブジェクトはこれに収まる）
- 型は読み替えない。整数の欄に `"4"` や `4.0` や `true` を書かない（同じ record が同じ JSON で書かれるように）。`record.json` も同じ
- `record.json` に置くオブジェクトの中の list（`submission.submitters` など）は、`record.json` に残す

### entry と配列

配列を持つ entry は、`entries.jsonl` の行に長さと digest（下）を書き、配列は FASTA に alias を見出しにして置く。alias はパッケージの中で一意で、空白の無い印字可能な ASCII、4,096 文字まで。配列を持たない entry は digest を書かない（長さだけを書いてもよいが、v3 の entry には長さの欄が無いので、そのパッケージは `unpack` で v3 に戻せない）。長さと digest はパッケージを書く側（ツール）が計り、受け取る側は `check` で計り直して確かめる。

### FASTA

- `sequences/` のすぐ下の、名前が `.fa` で終わるファイル。名前は英数字と `_`、`-`、`.` で、`.` で始めない（どの OS のファイル名にもなるように）。幾つに分けてもよく、分け方は record に書かない（読む側は alias で配列を引くので、どう分けても同じ record になる）。配列の無いファイルは入れない
- 見出しは `>` と entry の alias だけ。説明を続けない
- 配列の行は ASCII の英字だけ。1 行の長さは問わない（1 本を 1 行に書いてもよい）。大文字でも小文字でもよい。改行は LF か CRLF。空の行は読み飛ばす
- 長さ 0 の配列は、見出しだけで配列の行が無いもの
- `sequence_digest` を持つ entry の配列は、どれか 1 つのファイルに 1 度だけ現れる。FASTA の配列は、どれも `sequence_digest` を持つ entry のもの
- どの英字を使えるか（塩基配列の IUPAC、アミノ酸）は、ここでは確かめない。ddbj-validator のルールが確かめる

### digest

GA4GH refget（v2）の `sha512t24u` に `SQ.` を付けたもの。配列を大文字にして SHA-512 を計り、先頭 24 バイトを base64url にする（`ACGT` なら `SQ.aKF498dAxcJAqme6QYQ7EZ07-fiw8Kw2`）。

- 改行と大文字小文字に左右されないので、FASTA の書き方が違っても同じ配列は同じ digest になる。refget は英字以外を除いてから計るが、パッケージの FASTA は英字以外を許さないので、同じ値になる
- `sha512t24u` は GA4GH の配列の識別子（refget v2、VRS）で、配列を内容で指すのに使える。refget v2 が必ず答えるのは MD5 で、ENA の refget も今は MD5 でしか引けないので、よその仕組みから引くときは MD5 を別に計る（[選ばなかった案](#選ばなかった案)）
- 大文字と小文字を区別しないので、配列の大文字小文字の違い（soft-masking）は digest にも、record の差分にも出ない。INSDC の flat file も塩基配列を小文字、アミノ酸を大文字で書くので、失うものは無い

## 確かめること

`check`（`ddbj_record_package check`）は次を確かめ、外れたものを挙げる。どのファイルも流して読み、壊れたパッケージ（目次が壊れている、CRC が合わない、圧縮が読めない）でも例外にせず問題として挙げる。`record.json` が壊れていても、JSON Lines と FASTA は確かめる。

- ファイルの先頭と zip の目次の先頭が、無圧縮で extra field の無い `mimetype` で、中身が合っている
- `record.json` があり、v4 のモデルに合い、JSON Lines に置く list を持たない
- メンバーが上のものだけ。名前とパス、圧縮、暗号化が上のとおり。使えない圧縮や暗号化のメンバーは、中を読まない
- `record.json` の `schema_version` が `v4`
- JSON Lines の各行が、その list の要素のモデルに型を読み替えずに合う。空のファイル、空の行、行の途中の CR、I-JSON でないもの（BOM、`NaN`、倍精度で表せない数、対になっていないサロゲート、同じ key の繰り返し）は問題
- FASTA の見出しが alias だけで、配列の行が英字だけ
- entry と配列が 1 対 1 で、長さと digest が合う。alias は一意

使うメモリは、配列の大きさにも JSON Lines の行の数にもよらない。FASTA は決まった大きさの塊ずつ、JSON Lines は 1 行ずつ読み、1 行と `record.json` には上限がある。増えるのは、配列を持つ entry の数に比例して覚えておく alias と長さと digest だけ。挙げる問題の数にも上限があり、壊れたファイルが問題の一覧でメモリを使い切ることは無い。外から受け取ったパッケージを確かめるなら、メモリを限った別のプロセスで行う（わざと作った入力では、上限の中の 1 行でもモデルに合わせるのに大きなメモリを使う）。

`check` が確かめるのはパッケージの形と、entry と配列の対応まで。feature の `sequence_id` が entry の alias を指しているか、relation の `index` が list の中にあるか、といった record の中の参照は、ddbj-validator のルールが確かめる。型が保証する範囲の考え方は v3 と同じ（[v3-schema.md](./v3-schema.md#型が保証する範囲)）。

`read_record` は `record.json` だけを読む。zip は末尾の目次からメンバーを直接取り出せるので、JSON Lines と FASTA がどれだけ大きくても、読むのは目次と `record.json` の分で済む。オブジェクトストレージの範囲読み出しでもできる。読む関数（`read_record`、`iter_objects`、`load_record`）は、`check` と同じ約束で読み、合わないものがあれば読むのを止める（黙って飛ばすと、後の行の位置がずれる）。

`features.jsonl` の並びは決めない（canonical JSON の並べ方に任せる）。entry ごとに feature を書く flat file を流して作るなら、読む側が `sequence_id` で引く索引を作る。

## canonical JSON との関係

パッケージは record の置き方で、record そのもの（`load_record` が組み立てるもの）は v3 の record と同じ形をしている。ddbj-repository の canonical JSON と JSON Patch の連鎖は、同じ record を相手にする。

- 行の順は list の順なので、JSON Patch のパス `/samples/3` は `samples.jsonl` の 4 行目に当たる。要素を足したり除いたりすれば、後の行が 1 つずつずれる
- canonical な形は、`record.json` と JSON Lines の行ごとに作れる。record の SHA は、`record.json` の SHA と、JSON Lines をファイルの名前の順、行の順に並べた SHA から組む（組み方は ddbj-repository の canonical JSON で決める）。1 つの sample を直せば、変わるのはその行と record の SHA だけ
- FASTA の分け方は record に入らないので、分け方を変えても record の SHA は変わらない
- `sequence_digest` を通じて、record の SHA は配列も含む。配列が変われば digest が変わり、record の差分にはその 1 行が出る。配列を差分や JSON Patch に載せなくてよい

## パッケージに入れないもの

DRA のリードや GEA のデータファイルは、これまでどおりパッケージに入れず、別にアップロードして `File`（名前とチェックサム）で指す。それらは record とは別に持ち運ばれるデータファイルで、record は名前で指すだけでよい。配列は entry そのものを成すもので、record と一緒に動かないと record が意味を成さないので、パッケージに入れる。

## v3 から変わるもの

- record は、配列を持たなくてもパッケージで渡す。`schema_version` は `v4`
- entry は配列を持たず、長さと digest を持つ
- v3 の record は `pack` で v4 に、v4 のパッケージは `unpack` で v3 に移せる。どちらも record 全体と配列をメモリに載せる（`pack` は配列の数倍）ので、小さい record と移し替え用。ゲノムのパッケージは、配列を流して書くツールで作る
- `pack` は、v3 のモデルに合わない record と、`schema_version` が `v3` でない record を断る。型は読み替えない（v3 の型は `"12"` を整数の欄に受け付けるが、`pack` はその record を断る）。パッケージは型を読み替えずに読む約束なので（[JSON Lines](#json-lines)）、読み替えて書くと、同じ record が書く道具によって違う JSON になる。空の入れ物（`{"submission": {}}` など）は、空は無いのと同じとして残さない
- `unpack` は、配列を持たずに長さだけを書いた entry のあるパッケージを断る。v3 の entry には長さを置く場所が無く、黙って落とすと戻した record が元と違う

## 選ばなかった案

- **v3 のまま変える。** v3 を 1 つの JSON として読んでいるもの（ddbj-repository、ddbj-validator）が全て壊れる
- **配列を持たない record は JSON のまま認める。** 読む側が JSON と zip の 2 つを受けることになり、BioSample のように配列が無くても大きい record は、結局 JSON Lines を要する
- **配列を JSON Lines の entry の行に書く。** ゲノムでは 1 行が 1 GB を超え、行を丸ごと読む JSON では大きな JSON の問題が戻る
- **大きい list だけを JSON Lines に出す。** どの大きさから出すかの線に根拠が無く、同じ list が record によって `record.json` にも JSON Lines にもあることになり、読む側が 2 通りになる
- **FASTA のファイルの一覧を record に書く。** 分け方を変えただけで record が変わり、canonical な SHA と差分に出る。`sequences/` の下に置くことで足りる
- **FASTA を bgzip（ブロックごとの gzip）にして索引を付ける。** 1 本の配列だけを途中から取り出せるが、zip の中に別の圧縮と索引を持ち込むことになる。flat file の生成も検証も配列を頭から全て読むので、1 本だけを取り出す場面が今は無い
- **FASTA を無圧縮にする。** 範囲読み出しで 1 本だけ取り出せるが、塩基配列がおよそ 3 分の 1 に縮むのを捨てる理由が、上と同じく今は無い
- **digest を MD5 にする（refget v2 が必ず答え、CRAM の参照配列の M5 も MD5）。** よその仕組みから引くには今はこちらが便利だが、配列を内容で指す識別子（履歴、差分）には衝突に強いものを使いたい。GA4GH の識別子も `sha512t24u` に移っている。MD5 が要るところでは、その場で計れば済む
- **digest を配列の SHA-256 にする。** 大文字小文字の扱いを自分で決めることになり、ほかの仕組みとは突き合わせられない
