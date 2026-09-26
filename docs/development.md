# 開発

## 開発環境

開発環境は Docker Compose で立て、コマンドは container の中で実行する。

```bash
docker compose up -d --build
docker compose exec app uv run pytest
docker compose exec app uv run ruff check
docker compose exec app uv run ruff format --check
docker compose exec app uv run mypy
```

- 依存は image を作るときに `/opt/venv` に入れる。venv を repo の外に置くので、host に `.venv` はできない
- 依存を変えたら `docker compose exec app uv lock` で `uv.lock` を直し、`docker compose up -d --build` で image を作り直す
- compose は container を host のユーザー (既定は `1000:1000`) で動かす。container が repo に書いたファイルは host のユーザーのものになる

## CI

main への push と pull request で、GitHub Actions が次を実行する。

- ruff check、ruff format --check、mypy
- Python 3.10 - 3.14 で pytest
- 依存の下限 (`uv sync --resolution lowest-direct`) で pytest

## 依存と Python の範囲

利用側がなるべく入れやすいように、依存と Python の範囲を広く取る。

- 実行時の依存は pydantic だけにする。テストと lint の道具は `[dependency-groups] dev` に置き、利用側には見せない
- 依存と `requires-python` には下限だけを書き、上限は書かない。下限は CI の lowest-direct のテストで確かめる
- `requires-python` は 3.10 以上。型の注釈に `X | None` を使い、pydantic がそれを実行時に評価するため
- パッケージの version は `0.0.0` のまま変えない ([versioning.md](./versioning.md))

## lint と型検査

- ruff は既定の規則を使う。規則を外すときは `pyproject.toml` に理由と一緒に書く
- mypy は strict と pydantic の plugin で `ddbj_record/` を見る

## JSON Schema

JSON Schema は repo で管理しない。型から作れるので、commit すると型の変更のたびに JSON Schema の commit が要り、型との食い違いも起きるためである。要るときに書き出す ([usage.md](./usage.md))。

## 型と docs の書き方

- フィールドの意味は、`ddbj_record/schema/v*.py` の docstring とコメントに書く。docs/ には書き写さない
- docs/ には方針だけを書く。1 ファイル 1 トピックにし、README の docs の一覧に 1 行の説明を足す
- 型を変えたら、fixture と対応表も手で直す ([tests/README.md](../tests/README.md))
