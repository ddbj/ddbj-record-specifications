"""docs/v3-*-mapping.yml を読んで確かめるテストの共通部品。"""

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]


def _load_script_module(name: str, path: Path) -> ModuleType:
    """scripts/ の下のファイルを module として読む。

    一度読んだものは sys.modules から返す (build_mapping.py が import する v3_locations を二重に
    読まないため)。読むあいだにスクリプトが足す sys.path は、読み終えたら元に戻す。
    """
    if name in sys.modules:
        return sys.modules[name]

    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module

    saved = list(sys.path)
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[name]
        raise
    finally:
        sys.path[:] = saved
    return module


# 対応表の場所の読み方 (書き方と、場所から型への解決) は、対応表を書くスクリプトと共有する。
v3_locations = _load_script_module("v3_locations", ROOT.joinpath("scripts/v3_locations.py"))

CONTAINER: str = v3_locations.CONTAINER
SEGMENT: re.Pattern[str] = v3_locations.SEGMENT
resolve = v3_locations.resolve
strip_note = v3_locations.strip_note
SCALARS = (str, int, float, bool)


def load_script(relative: str) -> ModuleType:
    """scripts/ の下のスクリプトを module として読む。名前は置き場所から作る (sra と gea の build_mapping を分ける)。"""
    return _load_script_module(relative.removesuffix(".py").replace("/", "."), ROOT.joinpath(relative))


class _UniqueKeyLoader(yaml.SafeLoader):
    """同じ key が 2 度書かれていたら、後の方で黙って上書きせずに失敗する。"""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        keys = [self.construct_object(key, deep=deep) for key, _ in node.value]
        duplicates = {key for key in keys if keys.count(key) > 1}
        if duplicates:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate keys: {sorted(duplicates)}", node.start_mark
            )
        return super().construct_mapping(node, deep=deep)


def load_mapping(name: str) -> dict[str, dict[str, str]]:
    return yaml.load(  # type: ignore[no-any-return]
        ROOT.joinpath("docs", name).read_text(encoding="utf-8"),
        Loader=_UniqueKeyLoader,  # noqa: S506 -- a SafeLoader subclass
    )


def load_record(name: str) -> Any:
    return json.loads(ROOT.joinpath("tests/fixtures/v3/records", name).read_text(encoding="utf-8"))


def rows(mapping: dict[str, dict[str, str]]) -> dict[str, str]:
    """対応表の行ごとの v3 の場所。値を持たない入れ物は除く。"""
    return {
        f"{part}:{item}": location
        for part, items in mapping.items()
        for item, location in items.items()
        if location != CONTAINER
    }


def _matches(item: Any, annotation: str) -> bool:
    """`[part_of sample]` や `[primary]` の注記に合う要素か。

    注記の語は順に、要素の type と、relation なら target.db に当たる。
    """
    words = annotation.split()
    if not words:
        return True
    if not isinstance(item, dict):
        return False

    actual = [item.get("type"), (item.get("target") or {}).get("db")]
    assert len(words) <= len(actual), f"cannot read the note [{annotation}]"

    return words == actual[: len(words)]


def values_at(data: Any, location: str) -> list[Any]:
    """location にある値を、list の注記に合う全ての要素にわたって集める。"""
    found = [data]

    for segment in strip_note(location).split("."):
        m = SEGMENT.fullmatch(segment)
        assert m, segment
        name, bracket = m.groups()

        found = [item[name] for item in found if isinstance(item, dict) and item.get(name) not in (None, "")]

        if bracket is not None and bracket.startswith("["):
            annotation = bracket[1:-1]
            found = [element for items in found for element in items if _matches(element, annotation)]
        elif bracket is not None:
            key = bracket[1:-1]
            found = [items[key] for items in found if key in items]

    return found
