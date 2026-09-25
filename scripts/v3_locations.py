"""Reading the v3 locations written in docs/v3-*-mapping.yml.

A location is a dotted path into DdbjRecord: `experiments[].pool.members[].sample.id`.
`[...]` is an element of a list and `{...}` a value of a dict; what is inside the brackets, and a
trailing ` (...)`, are notes for the reader. `(container)` marks an element that holds no value
of its own.

Shared by scripts/*/build_mapping.py and the tests of the mappings.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from types import NoneType, UnionType
from typing import Any, Union, get_args, get_origin, get_type_hints

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ddbj_record.schema.v3 import DdbjRecord

CONTAINER = "(container)"

SEGMENT = re.compile(r"(\w+)(\[[^\]]*\]|\{[^}]*\})?")

# The kinds of stored value (as the census scripts name them) each v3 type can hold.
READABLE_AS = {int: {"int", "empty"}, float: {"int", "float", "empty"}, bool: {"bool", "empty"}}


def strip_note(location: str) -> str:
    return re.sub(r" \(.*\)$", "", location)


def segments(location: str) -> list[str]:
    """The location's segments, with the notes inside brackets dropped."""
    return [re.sub(r"\[[^\]]*\]", "[]", segment) for segment in strip_note(location).split(".")] if location else []


def _unwrap_optional(tp: Any) -> Any:
    if get_origin(tp) in (Union, UnionType):
        args = [a for a in get_args(tp) if a is not NoneType]
        if len(args) != 1:
            raise TypeError(tp)
        return args[0]
    return tp


def resolve(location: str) -> Any:
    """The type at a location. Raises LookupError when the location does not exist in the model."""
    tp: Any = DdbjRecord

    for segment in strip_note(location).split("."):
        m = SEGMENT.fullmatch(segment)
        if not m:
            raise LookupError(f"{location}: cannot read {segment!r}")
        name, bracket = m.groups()

        if not (isinstance(tp, type) and issubclass(tp, BaseModel)):
            raise LookupError(f"{location}: {name} is below a non-model")  # noqa: TRY004 -- the location is wrong, not a type
        if name not in tp.model_fields:
            raise LookupError(f"{location}: {tp.__name__} has no field {name!r}")

        # Annotations naming a model defined later (RelationTarget, File) are still strings.
        tp = _unwrap_optional(get_type_hints(tp)[name])
        container = get_origin(tp)

        if bracket is None:
            if container in (list, dict):
                raise LookupError(f"{location}: {name} is a {container.__name__}")
        elif bracket.startswith("["):
            if container is not list:
                raise LookupError(f"{location}: {name} is not a list")
            tp = get_args(tp)[0]
        else:
            if container is not dict:
                raise LookupError(f"{location}: {name} is not a dict")
            tp = get_args(tp)[1]

    return tp


def unreadable(tp: Any, kinds: set[str]) -> set[str]:
    """The kinds of stored value that tp (a type resolve returned) cannot hold."""
    return kinds - READABLE_AS[tp] if tp in READABLE_AS else set()
