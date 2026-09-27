# 使い方

## インストール

```bash
pip install "ddbj-record @ git+https://github.com/ddbj/ddbj-record-specifications.git@v3.1"
```

使う major の系統の tag (minor) か commit で固定する。v3 は main、v1 / v2 は `v2` branch の系統である ([versioning.md](./versioning.md))。

GitHub の archive (`archive/<commit>.tar.gz`) で入れることもできる。version は archive の中の `.git_archival.txt` から付く。そのため、tag が打たれる前と後で、同じ commit の archive の中身が変わる。archive をハッシュで固定するなら、tag が打たれた後に取る。

## record を読む

major ごとの型 `DdbjRecord` で読む。読めなければ `pydantic.ValidationError` になる。

```python
from pathlib import Path

from ddbj_record.schema.v3 import DdbjRecord

record = DdbjRecord.model_validate_json(Path("record.json").read_text())
```

v1 / v2 の record は、`v2` の系統の `ddbj_record.schema.v1` / `ddbj_record.schema.v2` の `DdbjRecord` で読む。

型が保証するのは、JSON として読めて型に合うことまでである。登録データとして正しいかは [ddbj/ddbj-validator](https://github.com/ddbj/ddbj-validator) で確かめる。

## major の間の変換

今あるのは v1 <-> v2 の converter で、`v2` の系統にある。

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

## JSON Schema

`dump_json_schema` が、major ごとの JSON Schema を標準出力に書く。JSON Schema は repo で管理していないので、要るときにこれで書き出す。

```bash
dump_json_schema --version v3 > ddbj_record.schema.json
```

pydantic が出す形のままで、共通の型は `$defs` にまとめ、`$ref` で指す。
