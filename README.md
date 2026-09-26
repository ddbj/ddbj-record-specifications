# DDBJ Record Specifications

DDBJ の登録データを表す JSON (DDBJ Record) の型を、Pydantic で定義する Python パッケージ。

この repo が持つもの:

- major ごとの型 (`ddbj_record/schema/v*.py`)。JSON Schema もここから作る
- major の間の converter (`ddbj_record/converter/`)
- v4 のパッケージ (record を 1 つの zip にしたもの) を確かめ、v3 と行き来するもの (`ddbj_record/package.py`)

持たないもの:

- 登録データとしての正しさの検証。[ddbj/ddbj-validator](https://github.com/ddbj/ddbj-validator) のルールが判定する
- XML など、各 DB の形式との変換。[ddbj/ddbj-repository](https://github.com/ddbj/ddbj-repository) などの利用側が持つ

## docs

- [docs/usage.md](./docs/usage.md): インストール、record の読み方、major の間の変換、JSON Schema の書き出し
- [docs/versioning.md](./docs/versioning.md): major の分け方、major の中の変更、利用側からの PR の受け入れ方
- [docs/v3-schema.md](./docs/v3-schema.md): v3 のモデルのまとめ方、型が保証する範囲、元の形式との往復、識別子と relations
- [docs/v4-schema.md](./docs/v4-schema.md): v4 のパッケージ (record.json、JSON Lines、FASTA の zip) の形と約束、v3 との行き来
- [docs/v1-v2.md](./docs/v1-v2.md): 古い major の v1 / v2 の位置づけ、schema_version の読み方、v1 と v2 の間の変換
- [docs/development.md](./docs/development.md): 開発環境、CI、依存と Python の範囲、lint、型と docs の書き方
- [tests/README.md](./tests/README.md): テストが確かめること、テストデータの作り方

## ライセンス

[Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0)。[LICENSE](./LICENSE) を参照。
