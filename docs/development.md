# 開発

## 開発環境

開発環境は Docker Compose で立て、コマンドは container の中で実行する。

```bash
docker compose up -d --build
docker compose exec app uv run pytest
docker compose exec app uv run ruff check ddbj_record/ tests/
docker compose exec app uv run ruff format --check ddbj_record/ tests/
docker compose exec app uv run mypy
```

main に push すると、CI が同じ pytest / ruff / mypy を Python 3.10 - 3.13 で実行する。
テストの方針は [tests/README.md](../tests/README.md) にある。

## JSON Schema の書き出し

```bash
docker compose exec app uv run dump_json_schema --version v3
```

repo の `schemas/v3/ddbj_record.schema.json` に書く。`schemas/` は git で管理しない。
書き出し先は、`ddbj_record/` から親のディレクトリをたどって最初に見つかる `pyproject.toml` の場所で決まる。pip で入れた環境では、書き出し先が見つからないか、別の project の中に書いてしまうので使わない。

## 型と docs の書き方

- フィールドの意味は、`ddbj_record/schema/v*.py` の docstring とコメントに書く。docs/ には書き写さない
- docs/ には方針だけを書く。1 ファイル 1 トピックにし、README の docs の一覧に 1 行の説明を足す
- 型を変えたら、fixture と対応表も手で直す ([tests/README.md](../tests/README.md))
