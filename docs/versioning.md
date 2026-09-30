# version の方針

DDBJ Record の version は major (v1 / v2 / v3 / v4) だけで表す。

## major の分け方

major ごとに `ddbj_record/schema/v1.py` / `v2.py` / `v3.py` / `v4.py` を持つ。REST API が `/v1` と `/v2` を並べて提供するのと同じ考え方である。

- 次の major は、main の上に新しいファイルとして作る。branch では作らない
- 新しい major を出した後も、古い major は main の上で直す
- 古い major のファイルは消さない

1 つのパッケージに全ての major が入っているので、1 つの環境で複数の major を同時に import できる。

```python
from ddbj_record.schema.v2 import DdbjRecord as V2Record
from ddbj_record.schema.v3 import DdbjRecord as V3Record
```

これで次のことができる。major を git の tag や branch で分けると、pip は 1 つの環境に 1 つの version しか入れられないので、どれもできなくなる。

- major の間の converter を書く (v1 の record を読んで v2 の record を書く `ddbj_record/converter/v1_to_v2.py` など)
- 古い major と新しい major の record が混ざって保存されているときに、両方を読む
- 利用側を少しずつ新しい major に移す

## minor と tag

minor と git tag は使わない。

- v3 と v4 の record の `schema_version` は `"v3"` / `"v4"` と書く。minor は付けない
- パッケージの version (hatch-vcs が git から付ける値) には意味を持たせない。新しい tag は打たず、GitHub Release も作らない
- 利用側は main の最新を追うか、commit を指定して固定する

v1 / v2 の record には、minor 付きの `schema_version` が残っている。v1 / v2 の型はこれを読み、その major の最新の minor にそろえる。例えば v2 の型は、`"0.2"` も `"v2.0"` も `"v2.3"` として読む。

## major の中の変更

major の中でも、フィールドの削除・名前の変更・型の変更をしてよい。
release note・CHANGELOG は書かない。利用側には PR の本文で知らせ、利用側は自分のテストで変更に気づいて追随する。

その代わり、破壊的変更になりにくい定義を選ぶ。

- 新しい情報は、既存のフィールドの意味を変えずに、新しいフィールドとして足す
- 選択肢が増えそうな値は enum (`Literal`) にせず `str` にし、許す値は ddbj-validator のルールで決める
- 元の形式で繰り返せるものは、手元の例が 1 つずつしか無くても list にする

## 利用側からの PR

利用側から上がってくる PR は、なるべくすぐ受け入れる。

- 使う現場で要るものは、この repo で止めない
- 受け入れた後に、この repo の側で形を整えることがある。その形に納得がいかなければ、改めて PR を出してもらう
