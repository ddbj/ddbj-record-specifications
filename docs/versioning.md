# version の方針

DDBJ Record の version は `vMAJOR.MINOR` (`v3.1` など) で表す。record は自分が書かれた形の version を `schema_version` に持ち、この repo は系統ごとに、その major の minor と同じ名前の git tag を打つ。

## major と系統

major ごとに系統を分け、それぞれ major の名前の branch (`v2`、`v3`) に置く。今の major も同じで、`main` は系統に使わない。GitHub の default branch は、最新の major の branch にする。

- 利用側は、使う major の branch を追うか、その tag か commit で型を固定する。branch の名前が「この major の中の変更だけが来る」ことを約束する。形の変わらない不具合の直しには tag を打たないので、それも追うなら branch を参照する
- 新しい major は、今の major の branch から切った branch (`v4` など) で作る。出来上がったら default branch をそこに切り替える。その間も、それより後も、今の major の branch を追う利用側には何も起きない
- 古い major の branch は消さない。不具合はそこで直す

`main` を最新の major にすると、次の major に取り掛かった時点で、`main` を今の major のつもりで追っていた利用側が壊れる。次の major に取り掛かるときに初めて今の major の branch を切っても、それまで `main` を追っていた利用側は同じように壊れる。

1 つの系統に入る型は 1 つの major のものである。例外は major の間の converter で、新しい方の系統に置き、古い major の型をそこに持つ。依存は新しい系統から古い系統への一方向で、古い系統は新しい系統を知らない (pydantic 2 が `pydantic.v1` を同梱しているのと同じ)。

- 古い major の型を別の系統から持ってくるときは、元の branch の commit を 1 つ決めてその写しを置き、元と同じ内容であることを確かめるテストを converter と一緒に足す。元の branch で直したら写しを取り直す
- v1 は v2 の系統に入っている。v1 と v2 の間の converter があり、利用側 (dr_tools) は両方を一緒に使うため

別の major の型を同じ環境に並べる必要は、converter の外には無い。pip は 1 つの環境に 1 つの version しか入れないが、利用側が読むのは 1 つの major の record である。複数の major の record が混ざって保存されていれば、converter で 1 つの major にそろえてから読む。

## minor

minor は、型の形が変わるたびに上げる。破壊的な変更かどうかは問わない。

- 形とは、型が受け付ける record の範囲と、型の名前 (Python から import する名前) である。説明 (`description` / `examples` / `title`) だけの変更は形を変えない
- 上げるのは `ddbj_record/schema/__init__.py` の `LATEST_MINOR_VERSIONS` で、形を変える PR の中で上げる
- 上げ忘れは CI の `minor` job が止める。今の minor の tag がすでにあり、その tag から形が変わっていれば落ちる。見るのは JSON Schema に出る形なので、JSON Schema に出ない validator を足すときは、PR を出す側が minor を上げ、下のラベルも付ける
- major の branch への変更は PR で入れ、CI と `label` workflow が通り、向き先に追いついてから merge する。ruleset でこれを merge の条件にする。同じ minor に上げた PR が 2 つ続けて入ると、後の方は merge した後の branch の CI で初めて落ちる。PR を通らない変更は release note にも載らない
- 系統の branch に入ると、CI の `tag` workflow がその minor の tag を打つ。打つのは系統の major の tag だけで、系統が持つ古い major の型の minor は `LATEST_MINOR_VERSIONS` にだけ書く
- 形の変わらない変更には tag を打たない。パッケージの version は tag から付き、tag の後の commit は `3.1.post1.devN+g…` のようになる

v3 の形はまだ動いているので、破壊的な変更も minor で出す (semver の `0.x` と同じ扱い)。v3 が落ち着いたと判断したら本書にそう書き、以降の破壊的な変更は次の major にする。

tag を打つ手間が CI の中で済むので、minor の数を減らす理由は無い。record が自分の形を言えないと、利用側は形の変わる前と後の record を見分けられず、それぞれの側で目印を作ることになる。

## schema_version

record を書く側は、使った型の `LATEST_MINOR_VERSIONS` の値を `schema_version` に書く (v3 なら今は `"v3.1"`)。

- v3 の型は record の minor を書き換えない。minor が違えば形が違い得るので、その record を書いた minor の tag の型で読むか、利用側で今の形に読み替える
- `"v3"` と `"v3.0"` は minor を持たなかった頃の値で、どの形かは保証しない。v3.1 から数えるのは、`"v3.0"` と書かれた record の多くが今と違う形 (`project` が list でなかった頃) だからである
- v1 / v2 の型は、これまでどおりどの minor も最新の minor として読む ([v1-v2.md](./v1-v2.md))

## major の中の変更

major の中でも、フィールドの削除・名前の変更・型の変更をしてよい。その代わり minor を上げ、利用側が直す必要があるかを知らせる。

- 形を変える PR には、`breaking` (利用側が直す必要がある) か `compatible` (今の利用側はそのまま動く) のラベルを 1 つ付ける。`label` workflow が PR の向き先と JSON Schema を比べ、形が変わっているのにラベルが 1 つでなければ落ちる。破壊的かどうかは、利用側にとっての意味で PR を出す側が決める。ラベルを付けられない人 (fork からの PR) の PR は、受け入れる側が付ける
- `tag` workflow は tag を打つと、その minor の GitHub Release を作る。release note は同じ major の前の minor からの PR を、「破壊的変更」「互換な変更」「その他」に分けて並べる (`.github/release.yml`)
- 変更の中身は PR の本文に書く。手で書く CHANGELOG は持たない

変更が利用側に及ばないよう、破壊的変更になりにくい定義を選ぶ。

- 新しい情報は、既存のフィールドの意味を変えずに、新しいフィールドとして足す
- 選択肢が増えそうな値は enum (`Literal`) にせず `str` にし、許す値は ddbj-validator のルールで決める
- 元の形式で繰り返せるものは、手元の例が 1 つずつしか無くても list にする

## 利用側からの PR

利用側から上がってくる PR は、なるべくすぐ受け入れる。

- 使う現場で要るものは、この repo で止めない
- 受け入れた後に、この repo の側で形を整えることがある。その形に納得がいかなければ、改めて PR を出してもらう

## この方針に移る手順

今は `main` が v1 / v2 / v3 を全部持ち、利用側の一部が `main` を参照している。`main` は消さずに今の形で止め、利用側が移るのを待つ。止めるので、`main` を参照している利用側は壊れない (その代わり、止めた後の変更は届かない)。

1. v3 の minor を `v3.1` とし、tag `v3.1` を打つ。v3 の record を書く利用側 (ddbj-repository など) は `schema_version` を `"v3.1"` にする
2. `main` から `v3` branch を作り、v1 / v2 の型と converter、v1 / v2 のためだけにある `normalize_schema_version` などと、その docs を消す
3. `main` から `v2` branch を作り、v3 の型とその docs を消す。tag `v2.3` は CI が打つ (系統の major は `SCHEMA_VERSIONS` の最後の値で決まるので、v3 を残すと `v2` に `v3.1` を打つ)
4. default branch を `v3` にし、開いている PR の向き先を `v3` に変える。`v2` / `v3` に ruleset を置き、PR を通すこと、CI と `label` workflow が通ること、向き先に追いついていることを merge の条件にする
5. `main` の README に `v2` / `v3` を追うよう書いてから、`main` に変更を受け付けない ruleset を置いて止める
6. 利用側を移す。dr_tools は `v2` (v1 / v2 は不具合を直すだけの系統なので、tag でなく branch を追うのが合う)、`main` を追っている他の利用側は `v3`
7. `main` を参照する利用側が無くなったら、`main` を消す
