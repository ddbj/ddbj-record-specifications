"""A change to the shape of the line's major raises its minor (docs/versioning.md).

The JSON Schema of the types is compared with the one at the tag of the current minor. The tag is
made once the minor reaches the branch, so a minor that is not tagged yet has nothing to compare with.

The comparison needs the tags. CI's `minor` job fetches them and sets REQUIRE_TAGS, so that a
checkout without them fails there instead of skipping.
"""

import json
import os
import subprocess
import sys
import tarfile
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from ddbj_record.schema import LATEST_MINOR_VERSIONS, SCHEMA_VERSIONS
from ddbj_record.schema.cli import dump_schema

ROOT = Path(__file__).resolve().parents[3]

# The major this line is for: its tags are the ones the `tag` workflow makes.
MAJOR = SCHEMA_VERSIONS[-1]

# Keywords that document a schema without changing which records it accepts.
_ANNOTATIONS = frozenset({"description", "examples"})

# Keywords whose value maps names to schemas. A field may itself be called `description`.
_SCHEMA_MAPS = frozenset({"properties", "$defs", "patternProperties"})


def _git(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=False)


def _shape(schema: Any) -> Any:
    if isinstance(schema, list):
        return [_shape(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    return {
        key: {name: _shape(sub) for name, sub in value.items()} if key in _SCHEMA_MAPS else _shape(value)
        for key, value in schema.items()
        if key not in _ANNOTATIONS
    }


def _schema_at(tag: str, tmp_path: Path) -> Any:
    archive = _git("archive", "--format=tar", tag, "ddbj_record")
    assert archive.returncode == 0, archive.stderr.decode()
    with tarfile.open(fileobj=BytesIO(archive.stdout)) as tar:
        tar.extractall(tmp_path, filter="data")

    # `python -c` puts its working directory first on sys.path, ahead of the installed package, so
    # running it in the extracted tree is what makes it import the tag's types and not the current ones.
    dumped = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from ddbj_record.schema.cli import dump_schema; print(dump_schema(sys.argv[1]))",
            MAJOR,
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(dumped.stdout)


def test_shape_is_that_of_the_minors_tag(tmp_path: Path) -> None:
    tag = LATEST_MINOR_VERSIONS[MAJOR]

    if not _git("tag", "--list").stdout.strip():
        if os.environ.get("REQUIRE_TAGS"):
            pytest.fail("this checkout has no tags; fetch them (actions/checkout with fetch-depth: 0)")
        pytest.skip("this checkout has no tags")
    if _git("rev-parse", "--quiet", "--verify", f"refs/tags/{tag}").returncode != 0:
        pytest.skip(f"{tag} is not tagged yet: it is tagged when it reaches the branch")

    assert _shape(json.loads(dump_schema(MAJOR))) == _shape(_schema_at(tag, tmp_path)), (
        f'the shape of {MAJOR} has changed since {tag}; raise LATEST_MINOR_VERSIONS["{MAJOR}"]'
    )
