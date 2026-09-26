# 使い方

## インストール

```bash
pip install git+https://github.com/ddbj/ddbj-record-specifications.git@main
```

main の最新を使うか、commit を指定して固定する。どちらを選ぶかの考え方は [versioning.md](./versioning.md) にある。

## record を読む

major ごとの型 `DdbjRecord` で読む。読めなければ `pydantic.ValidationError` になる。

```python
from pathlib import Path

from ddbj_record.schema.v3 import DdbjRecord

record = DdbjRecord.model_validate_json(Path("record.json").read_text())
```

v1 / v2 の record は `ddbj_record.schema.v1` / `ddbj_record.schema.v2` の `DdbjRecord` で読む。1 つの環境で複数の major を同時に import できる。

型が保証するのは、JSON として読めて型に合うことまでである。登録データとして正しいかは [ddbj/ddbj-validator](https://github.com/ddbj/ddbj-validator) で確かめる。

## major の間の変換

今あるのは v1 <-> v2 の converter である。

```bash
ddbj_record_converter --from v1 --to v2 --input v1.json --output v2.json
```

Python からは、変換元の major の型で読んだものを渡す。

```python
from pathlib import Path

from ddbj_record.converter.v1_to_v2 import v1_to_v2
from ddbj_record.schema.v1 import DdbjRecord as V1Record

v2_record = v1_to_v2(V1Record.model_validate_json(Path("v1.json").read_text()))
```

## v4 のパッケージ

v4 の record は、1 つの zip (パッケージ) で渡す ([v4-schema.md](./v4-schema.md))。`ddbj_record_package` で、パッケージが約束どおりかを確かめ、v3 の record と行き来する。

```bash
ddbj_record_package check record.ddbj.zip              # 約束どおりかを確かめる。外れたものを標準エラーに書き、1 で終わる
ddbj_record_package pack record.json record.ddbj.zip   # v3 の record を v4 のパッケージにする
ddbj_record_package unpack record.ddbj.zip record.json # v4 のパッケージを v3 の record に戻す
```

Python からは、`record.json` だけを読むことも、JSON Lines を 1 行ずつ読むこともできる。どちらもパッケージ全体をメモリに載せない。

```python
from pathlib import Path

from ddbj_record.package import iter_objects, read_record

record = read_record(Path("record.ddbj.zip"))  # v4 の DdbjRecord。JSON Lines に置く list は持たない
for sample in iter_objects(Path("record.ddbj.zip"), "samples.jsonl"):
    ...
```

`pack` と `unpack` は record 全体と配列をメモリに載せるので、小さい record と移し替えに使う。

## JSON Schema

`dump_json_schema` が、major ごとの JSON Schema を標準出力に書く。JSON Schema は repo で管理していないので、要るときにこれで書き出す。

```bash
dump_json_schema --version v3 > ddbj_record.schema.json
```

pydantic が出す形のままで、共通の型は `$defs` にまとめ、`$ref` で指す。
