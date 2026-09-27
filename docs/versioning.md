# version の方針

DDBJ Record の version は `vMAJOR.MINOR` (`v3.1` など) で表す。record は自分が書かれた形の version を `schema_version` に持ち、この repo は同じ名前の git tag を打つ。利用側は tag か commit で型を固定する。

## major と系統

major ごとに系統を分ける。最新の major は main で作り、古い major はその名前の branch (`v2` など) で直す。一般的なライブラリが major ごとに branch を持つのと同じ形である。

- 利用側は、使う major の系統を参照する
- 新しい major を始めるときは、main から今の major の branch を切り、main で新しい major を作る
- 古い major の branch は消さない。不具合はそこで直す

1 つの系統に入る型は 1 つの major のものである。例外は major の間の converter で、新しい方の系統に置き、古い major の型をそこに持つ。依存は新しい系統から古い系統への一方向で、古い系統は新しい系統を知らない (pydantic 2 が `pydantic.v1` を同梱しているのと同じ)。

- 古い major の型を別の系統から持ってくるときは、元の branch の commit を 1 つ決めてその写しを置き、同じ内容であることを CI で確かめる。元の branch で直したら写しを取り直す
- v1 は v2 の系統に入っている。v1 と v2 の間の converter があり、利用側 (dr_tools) は両方を一緒に使うため

別の major の型を同じ環境に並べる必要は、converter の外には無い。pip は 1 つの環境に 1 つの version しか入れないが、利用側が読むのは 1 つの major の record である。複数の major の record が混ざって保存されていれば、converter で 1 つの major にそろえてから読む。

## minor

minor は、型の形が変わるたびに上げる。破壊的な変更かどうかは問わない。

- 形とは、型が受け付ける record の範囲と、型の名前 (Python から import する名前) である。説明 (`description` / `examples`) だけの変更は形を変えない
- 上げるのは `ddbj_record/schema/__init__.py` の `LATEST_MINOR_VERSIONS` で、形を変える PR の中で上げる
- 上げ忘れは CI の `minor` job が止める。今の minor の tag がすでにあり、その tag から形が変わっていれば落ちる
- main (古い major ならその branch) に入ると、CI の `tag` workflow がその minor の tag を打つ。打つのは系統の major の tag だけで、系統が持つ古い major の型の minor は `LATEST_MINOR_VERSIONS` にだけ書く
- 形の変わらない変更には tag を打たない。パッケージの version は tag から付き、tag の後の commit は `3.1.post2.dev0+g…` のようになる

v3 の形はまだ動いているので、破壊的な変更も minor で出す (semver の `0.x` と同じ扱い)。v3 が落ち着いたと判断したら本書にそう書き、以降の破壊的な変更は次の major にする。

tag を打つ手間が CI の中で済むので、minor の数を減らす理由は無い。record が自分の形を言えないと、利用側は形の変わる前と後の record を見分けられず、それぞれの側で目印を作ることになる。

## schema_version

record を書く側は、使った型の `LATEST_MINOR_VERSIONS` の値を `schema_version` に書く (v3 なら今は `"v3.1"`)。

- v3 の型は record の minor を書き換えない。minor が違えば形が違い得るので、その record を書いた minor の tag の型で読むか、利用側で今の形に読み替える
- v3.1 より前の v3 の record は `"v3"` か `"v3.0"` と書かれている。minor を持たなかった頃の値で、どの形かは保証しない。v3.1 から数えるのは、`"v3.0"` と書かれた record の多くが今と違う形 (`project` が list でなかった頃) だからである
- v1 / v2 の型は、これまでどおりどの minor も最新の minor として読む ([v1-v2.md](./v1-v2.md))

## major の中の変更

major の中でも、フィールドの削除・名前の変更・型の変更をしてよい。その代わり minor を上げ、変更は PR の本文で知らせる。tag の間の差分は GitHub の比較 (`compare/v3.1...v3.2`) で見られるので、release note・CHANGELOG は書かない。

変更が利用側に及ばないよう、破壊的変更になりにくい定義を選ぶ。

- 新しい情報は、既存のフィールドの意味を変えずに、新しいフィールドとして足す
- 選択肢が増えそうな値は enum (`Literal`) にせず `str` にし、許す値は ddbj-validator のルールで決める
- 元の形式で繰り返せるものは、手元の例が 1 つずつしか無くても list にする

## 利用側からの PR

利用側から上がってくる PR は、なるべくすぐ受け入れる。

- 使う現場で要るものは、この repo で止めない
- 受け入れた後に、この repo の側で形を整えることがある。その形に納得がいかなければ、改めて PR を出してもらう

## この方針に移る手順

main はまだ v1 / v2 を持っている。次の順に移す。

1. v3 の minor を `v3.1` とし、tag `v3.1` を打つ
2. 今の main から `v2` branch を作り、そこから v3 の型を消す。tag `v2.3` は CI が打つ (系統の major は `SCHEMA_VERSIONS` の最後の値で決まるので、v3 を残すと `v2` に `v3.1` を打つ)
3. dr_tools の依存を main から `v2` の系統 (tag `v2.3` か commit) に移してもらう
4. main から v1 / v2 の型と converter を消す

3 より前に 4 をすると、main を参照している dr_tools と、それを入れる DFAST が壊れる。
