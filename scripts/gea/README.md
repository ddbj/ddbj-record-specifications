# GEA の対応表を作る

[docs/v3-gea-mapping.yml](../../docs/v3-gea-mapping.yml) は、次の 2 段で作る。手で直さない。

```sh
# 0. GEA の公開用の写しから、メタデータのファイルだけを持ってくる（1.4 GB。ほとんどは ADF）
rsync -a -m --include='*/' --include='livelist.txt' --include='*.idf.txt' --include='*.sdrf.txt' \
  --include='*.filelist.txt' --include='*.adf' --include='*.metadata' --exclude='*' \
  a012:/usr/local/resources/gea/ gea/

# 1. IDF / SDRF / ADF / CIBEX の項目を全て数える（十数秒）
uv run scripts/gea/census_gea.py gea census.json

# 2. 項目それぞれに v3 の場所を割り当てて書く
uv run scripts/gea/build_mapping.py census.json docs/v3-gea-mapping.yml
```

- 1 の出力は値の標本（名前など）を含むので、コミットしない。対応表に入るのは項目とファイルの数だけ
- 1 は、読み方の規則で読めても v3 に置けないもの（同じ名前の列の空の欄の後の値など）を `anomalies` の `unrepresentable:` として数える
- 2 は、次を確かめ、1 つでも外れれば挙げて何も書かない。新しい項目が現れたら、`build_mapping.py` に規則を足す
  - `unrepresentable:` が 0
  - 規則がある
  - 行き先が v3 のモデルにある
  - 1 つのファイル（IDF）、行（SDRF）、塊（CIBEX）の中で繰り返す項目が、自分の list に入る
  - `int` / `float` / `bool` の行き先に、その型で読めない値が保存されていない
- ファイルの読み方（引用符、文字コード、CIBEX の節と塊）は `census_gea.py` にあり、[docs/v3-gea.md](../../docs/v3-gea.md) に書いた
