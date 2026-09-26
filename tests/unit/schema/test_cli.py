import json

import pytest

from ddbj_record.schema.cli import dump_schema, main, parse_args

# === parse_args ===


@pytest.mark.parametrize(("raw", "expected"), [("v1", "v1"), ("v2", "v2"), ("v3", "v3"), ("v2.3", "v2")])
def test_parse_args_accepts_known_versions(raw: str, expected: str) -> None:
    assert parse_args(["--version", raw]).version == expected


@pytest.mark.parametrize("raw", ["v999", "draft", ""])
def test_parse_args_unknown_version_exits(raw: str) -> None:
    with pytest.raises(SystemExit):
        parse_args(["--version", raw])


# === dump_schema ===


@pytest.mark.parametrize(
    ("version", "keys"),
    [
        ("v1", ("COMMON", "COMMON_SOURCE", "ENTRIES")),
        ("v2", ("schema_version", "provenance", "submission", "sequences", "features")),
        ("v3", ("schema_version", "submission", "projects", "samples", "relations")),
    ],
)
def test_dump_schema_has_the_top_level_properties(version: str, keys: tuple[str, ...]) -> None:
    schema = json.loads(dump_schema(version))
    assert set(keys) <= set(schema["properties"])


def test_dump_schema_keeps_refs_to_defs() -> None:
    schema = json.loads(dump_schema("v3"))
    assert "$defs" in schema
    assert schema["properties"]["projects"]["anyOf"][0]["items"] == {"$ref": "#/$defs/Project"}


# === main ===


def test_main_writes_the_schema_to_stdout(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["dump_json_schema", "--version", "v3"])
    main()
    out = capsys.readouterr().out
    assert json.loads(out) == json.loads(dump_schema("v3"))
