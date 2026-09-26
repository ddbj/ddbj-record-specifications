# テストの方針

```bash
docker compose exec app uv run pytest
```

この repo のテストが確かめるのは、型が record を読めること、型と対応表が食い違っていないこと、converter の出力の 3 つである。登録データとしての正しさは確かめない (ddbj-validator のルールが判定する)。

## 型のテスト

- 各 major の fixture (`tests/fixtures/v1/`、`v2/`、`v3/records/`) が、その major の型で読めることを確かめる。`invalid_*.json` は読めないことを確かめる
- v3 の `*_full.json` は、なるべく多くのフィールドに値を入れた record である。v3 のモデルは `extra="forbid"` なので、型からフィールドを消すと `*_full.json` が読めなくなり、テストが落ちる。フィールドを消すときは、`*_full.json` も直す
- v2 の型が受け付ける値の範囲は、PBT (hypothesis) でも確かめる

## 対応表のテスト

[`tests/fixtures/v3/mapping/`](./fixtures/v3/mapping/) の対応表 (SRA / GEA) について、次を確かめる。

- 対応表の全ての場所が、v3 のモデルに実在する
- 値を持つ要素と属性は、値 (str / int / float / bool) のフィールドを指す
- 対応表の全ての場所に、`sra_full.json`・`gea_full.json`・`gea_array_design_full.json`・`gea_unread_sdrf.json` のどれかで値がある
- SRA は、[`tests/fixtures/v3/raw/dra/`](./fixtures/v3/raw/dra/) の XML に出てくる全ての要素と属性が、対応表にある

対応表の行が正しい場所を指しているか (TAG を value に置いていないか、など) は確かめない。それは対応表を読む人が決める。
型を変えたら、対応表も手で直す。

## converter のテスト

- 入力と期待する出力の組 ([`tests/fixtures/converter/`](./fixtures/converter/)) を持つ。converter の出力を `model_dump(exclude_none=True, by_alias=True)` した結果が、期待する出力と一致することを確かめる
- v1 -> v2 -> v1 と v2 -> v1 -> v2 の往復で、値が保たれることを確かめる
- PBT で、生成した record を変換した結果が、変換先の型で読めることを確かめる

## テストデータ

テストデータは、手書きの小さな JSON と、実データから作ったものの 2 種類を使う。

- 手書きの小さな JSON: 型を見ながら作り、必須のフィールド、典型的な構成、異常系、特殊なケースを 1 つずつ確かめる。生物学的に正しい必要はない
- 実データから作ったもの: 一度 commit したら、型を意図して変えない限り変えない

v1 / v2 の実データの出どころは次のとおり。DFC は細菌・古細菌向けの dfast_core、DFV はウイルス向けの DFAST_VRL である。

| fixture | 元のデータ |
|---|---|
| `v1/valid_dfc_gnm.json`、`v2/valid_dfc_gnm.json` | dr_tools の `examples/complete_genome.{ann,fa}` (DFC) |
| `v2/valid_dfv.json` | dr_tools の `examples/vrl_result.{ann,fa}` (DFV) |
| `v1/valid_wf_dfc_wgs.json`、`v2/valid_wf_dfc_wgs.json` | DFAST の DFC の実行結果 |
| `v2/valid_wf_dfv.json` | DFAST の DFV の実行結果 |

- どれも dr_tools の `drt_ann2json` で JSON にし、entry は最大 3 つ、feature は entry ごとに最大 5 つ、sequence は 100bp までに切り詰めた。location は元の座標のままなので、sequence より長い location がある
- `valid_wf_*` は template のまま実行した結果なので、submitter や organism が空文字列のものがある。実際の DFAST の出力の姿なので、そのまま許している
- v1 は DFC 専用の古い形式で、`trad_submission_category` が `Literal["WGS", "GNM"]` なので、DFV のデータは v2 にだけ置く

v3 の実データ (`tests/fixtures/v3/raw/`) の出どころは、[`tests/fixtures/v3/raw/README.md`](./fixtures/v3/raw/README.md) にある。
