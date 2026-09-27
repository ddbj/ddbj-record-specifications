"""A change to the shape of the line's major raises its minor (docs/versioning.md).

The JSON Schema of the types is compared with the one at the tag of the current minor. The tag is
made once the minor reaches the branch, so a minor that is not tagged yet has nothing to compare with.

The comparison needs the history and its tags. CI's `minor` job fetches them and sets REQUIRE_TAGS,
so that a checkout without them fails there instead of skipping.

Only what shows in the JSON Schema is compared. A validator added to a model narrows what it accepts
without showing there, and raising the minor for it is left to the PR that adds it.
"""

import json
import os
import re
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
_ANNOTATIONS = frozenset({"description", "examples", "title"})

# Keywords whose value maps names to schemas. A field may itself be called `description`.
_SCHEMA_MAPS = frozenset({"properties", "$defs", "patternProperties"})


def _git(*args: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=False)
    except FileNotFoundError:
        return subprocess.CompletedProcess(["git", *args], 127, b"", b"git is not installed")


def _has_history() -> bool:
    """Whether this is a git checkout with its whole history, and so with its tags."""
    return _git("rev-parse", "--is-shallow-repository").stdout.strip() == b"false"


def _require_history() -> None:
    if _has_history():
        return
    if os.environ.get("REQUIRE_TAGS"):
        pytest.fail("this checkout has no history to compare with; fetch it (actions/checkout with fetch-depth: 0)")
    pytest.skip("this checkout has no history to compare with")


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

    # The tag's types go first on sys.path, and the check that they are what got imported keeps an
    # installed package (or PYTHONSAFEPATH) from turning this into a comparison of the types with themselves.
    script = """
import sys
sys.path.insert(0, sys.argv[2])
import ddbj_record
assert ddbj_record.__file__.startswith(sys.argv[2]), ddbj_record.__file__
from ddbj_record.schema.cli import dump_schema
print(dump_schema(sys.argv[1]))
"""
    dumped = subprocess.run(
        [sys.executable, "-c", script, MAJOR, str(tmp_path.resolve())],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(dumped.stdout)


def _minor(version: str) -> int:
    return int(version.split(".")[1])


def test_minor_does_not_go_back() -> None:
    _require_history()

    tags = _git("tag", "--list", f"{MAJOR}.*").stdout.decode().split()
    tagged = [tag for tag in tags if re.fullmatch(rf"{MAJOR}\.\d+", tag)]
    latest = max(tagged, key=_minor, default=None)

    assert latest is None or _minor(LATEST_MINOR_VERSIONS[MAJOR]) >= _minor(latest), (
        f'LATEST_MINOR_VERSIONS["{MAJOR}"] is behind {latest}, which is tagged already'
    )


def test_shape_is_that_of_the_minors_tag(tmp_path: Path) -> None:
    tag = LATEST_MINOR_VERSIONS[MAJOR]

    _require_history()
    if _git("rev-parse", "--quiet", "--verify", f"refs/tags/{tag}").returncode != 0:
        pytest.skip(f"{tag} is not tagged yet: it is tagged when it reaches the branch")

    assert _shape(json.loads(dump_schema(MAJOR))) == _shape(_schema_at(tag, tmp_path)), (
        f'the shape of {MAJOR} has changed since {tag}; raise LATEST_MINOR_VERSIONS["{MAJOR}"]'
    )
