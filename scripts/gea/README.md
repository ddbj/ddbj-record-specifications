# GEA の対応表を作る

[docs/v3-gea-mapping.yml](../../docs/v3-gea-mapping.yml) は、次の 3 段で作る。手で直さない。

```sh
# 1. D-way の GEA の DB（dordb）から、IDF / SDRF / ADF の全ての版をファイルに書き出す（読むだけ。5 GB、ほとんどは ADF）
PGHOST=... PGPORT=... PGUSER=... PGPASSWORD=... PGDATABASE=dordb \
  ruby scripts/gea/export_dordb.rb dordb

#    CIBEX のファイルは dordb に無いので、GEA の公開用の写しから持ってくる
rsync -a -m --include='*/' --include='*.metadata' --exclude='*' a012:/usr/local/resources/gea/cibex/ cibex/

# 2. IDF / SDRF / ADF / CIBEX の項目を全て数える（数分）
uv run scripts/gea/census_gea.py dordb cibex census.json

# 3. 項目それぞれに v3 の場所を割り当てて書く
uv run scripts/gea/build_mapping.py census.json docs/v3-gea-mapping.yml
```

- 1 は Ruby 3.4 以上で動き、実行時に rubygems.org から `pg` を入れる。書き出すのは accession の振られたものだけ（振られる前の登録は移さない）。書き出す先は空でなければならない。`versions.tsv` は書き出した版の一覧で、IDF と SDRF の版を組んで record の版にするのに使う（[docs/v3-gea.md](../../docs/v3-gea.md#ddbj-repository-の側でやること)）。2 は、`fingerprint.json` の件数と書き出し先のファイルの数が合わなければ数えない
- 1 と 2 の出力は登録の中身を含むので、コミットしない。対応表に入るのは項目とファイルの数だけ
- 2 は、読み方の規則で読めても v3 に置けないもの（同じ名前の列の空の欄の後の値など）を `anomalies` の `unrepresentable:` として数える
- 3 は、次を確かめ、1 つでも外れれば挙げて何も書かない。新しい項目が現れたら、`build_mapping.py` に規則を足す
  - `unrepresentable:` が 0
  - 規則がある
  - 行き先が v3 のモデルにある
  - 1 つのファイル（IDF）、行（SDRF）、塊（CIBEX）の中で繰り返す項目が、自分の list に入る
  - `int` / `float` / `bool` の行き先に、その型で読めない値が保存されていない
- ファイルの読み方（引用符、文字コード、CIBEX の節と塊）は `census_gea.py` にあり、[docs/v3-gea.md](../../docs/v3-gea.md) に書いた
