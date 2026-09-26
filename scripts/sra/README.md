# SRA XML の対応表を作る

[docs/v3-sra-mapping.yml](../../docs/v3-sra-mapping.yml) は、次の 3 段で作る。手で直さない。

```sh
# 1. SRA XSD の全版から、要素と属性のパスを集める
uv run scripts/sra/inventory_xsd.py path/to/dracommon/generator/xjc/xsd/SRA.1.0 inventory.json

# 2. D-way（drmdb）に保存された全ての DRA 文書から、パスと値の種類を集める（読むだけ。8 百万文書で 1 時間半ほど）
PGHOST=... PGPORT=... PGUSER=... PGPASSWORD=... PGDATABASE=drmdb \
  ruby scripts/sra/census_drmdb.rb census.json

# 3. 1 と 2 のパスそれぞれに v3 の場所を割り当てて書く
uv run scripts/sra/build_mapping.py inventory.json census.json docs/v3-sra-mapping.yml
```

- 1 の XSD は D-way の dracommon にある（公開されていない）
- 2 と、下の `checks_drmdb.rb` は Ruby 3.4 以上で動き、実行時に rubygems.org から `pg` と `nokogiri` を入れる
- 2 の出力は値の標本（名前やメールアドレス）を含むので、コミットしない。対応表に入るのはパスと文書の数だけ
- 3 は、パスごとに次を確かめ、1 つでも外れれば挙げて何も書かない。XSD や保存された文書に新しいパスが現れたら、`build_mapping.py` に規則を足す
  - 規則がある
  - 行き先が v3 のモデルにある
  - 値を持たない入れ物とした要素が文字列を持っていない
  - 繰り返す要素が、自分の list に入る
  - `int` / `float` / `bool` の行き先に、その型で読めない値が保存されていない

[docs/v3-sra.md](../../docs/v3-sra.md) が引く数のうち、2 で出ないもの（accession の数、整形式でない文書、空の `TAG`、submission あたりの study の数、alias の重なり）は次で出す。

```sh
PGHOST=... PGPORT=... PGUSER=... PGPASSWORD=... PGDATABASE=drmdb \
  ruby scripts/sra/checks_drmdb.rb checks.json
```
