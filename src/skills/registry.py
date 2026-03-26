"""技能注册表。

加载顺序：
1. 内置技能 (builtin_tools)
2. pip 包 entry_points (openclaw_bot.skills)
3. config 中 extra_modules 指定的模块
4. src/skills/plugins/*.py 本地插件

插件需导出：
- TOOL_DEFINITIONS: list[dict]
- async def run_tool(name, args, *, chat_id, vector_query_fn) -> str | None
"""
from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
import json
import logging
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any, Awaitable, Callable

from src.core.config import settings
from src.skills import builtin_tools

logger = logging.getLogger(__name__)
Runner = Callable[..., Awaitable[str | None]]

_loaded = False
_defs: list[dict[str, Any]] = []
_runners: list[Runner] = []
_skill_names: list[str] = []


def _tool_name(defn: dict) -> str:
    return str(defn.get("function", {}).get("name", ""))


def _merge_defs(*lists: list[dict]) -> list[dict]:
    merged: OrderedDict[str, dict] = OrderedDict()
    for lst in lists:
        for d in lst:
            n = _tool_name(d)
            if n:
                merged[n] = d
    return list(merged.values())


def _load_entry_points() -> list[Any]:
    mods: list[Any] = []
    try:
        eps = importlib.metadata.entry_points(group="openclaw_bot.skills")
    except Exception:
        return mods

    for ep in eps:
        try:
            mod = ep.load()
            if hasattr(mod, "TOOL_DEFINITIONS") and hasattr(mod, "run_tool"):
                mods.append(mod)
                _skill_names.append(ep.name)
                logger.info("Loaded skill (entry_point): %s", ep.name)
        except Exception as e:
            logger.warning("Failed to load entry_point skill %s: %s", ep.name, e)
    return mods


def _load_extra_modules() -> list[Any]:
    mods: list[Any] = []
    extra = settings.get("skills.extra_modules") or []
    if not isinstance(extra, list):
        return mods

    for path in extra:
        if not path or not isinstance(path, str):
            continue
        try:
            mod = importlib.import_module(path.strip())
            if hasattr(mod, "TOOL_DEFINITIONS") and hasattr(mod, "run_tool"):
                mods.append(mod)
                _skill_names.append(path)
                logger.info("Loaded skill (extra_module): %s", path)
        except Exception as e:
            logger.warning("Failed to load extra_module %s: %s", path, e)
    return mods


def _load_plugins() -> list[Any]:
    if not settings.get("skills.enable_plugins", True):
        return []

    plugin_dir = Path(__file__).resolve().parent / "plugins"
    if not plugin_dir.is_dir():
        return []

    disabled = set(settings.get("skills.disable_plugins") or [])
    mods: list[Any] = []

    for path in sorted(plugin_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue

        name = path.stem
        if name in disabled:
            logger.info("Skipped skill (disabled): %s", name)
            continue

        mod_name = f"_skill_{name}"
        spec = importlib.util.spec_from_file_location(mod_name, path)
        if spec is None or spec.loader is None:
            continue

        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            logger.warning("Failed to load plugin %s: %s", path, e)
            sys.modules.pop(mod_name, None)
            continue

        tools = getattr(mod, "TOOL_DEFINITIONS", None)
        runner = getattr(mod, "run_tool", None)
        if not tools or not callable(runner):
            continue
        if not isinstance(tools, list):
            logger.warning("Invalid TOOL_DEFINITIONS (not a list): %s", path)
            continue

        mods.append(mod)
        _skill_names.append(name)
        logger.info("Loaded skill (plugin): %s", name)

    return mods


def _ensure_loaded() -> None:
    global _loaded, _defs, _runners
    if _loaded:
        return
    _loaded = True

    all_mods: list[Any] = []
    all_mods.extend(_load_entry_points())
    all_mods.extend(_load_extra_modules())
    all_mods.extend(_load_plugins())

    def_lists = [builtin_tools.TOOL_DEFINITIONS] + [
        getattr(m, "TOOL_DEFINITIONS", []) for m in all_mods
    ]
    _defs = _merge_defs(*def_lists)
    _runners = [m.run_tool for m in all_mods] + [builtin_tools.run_tool]


def get_tool_definitions() -> list[dict[str, Any]]:
    _ensure_loaded()
    return list(_defs)


def get_loaded_skill_summary() -> str:
    _ensure_loaded()
    names = [_tool_name(d) for d in _defs]
    return ", ".join(names) if names else "none"


async def dispatch_tool(
    name: str, arguments_json: str, chat_id: str, vector_query_fn
) -> str:
    _ensure_loaded()
    try:
        args = json.loads(arguments_json or "{}")
    except json.JSONDecodeError:
        args = {}

    for runner in _runners:
        try:
            out = await runner(name, args, chat_id=chat_id, vector_query_fn=vector_query_fn)
        except Exception as e:
            logger.exception("Tool execution failed: %s", name)
            return f"Error ({type(e).__name__}): {e}"
        if out is not None:
            return out

    return f"Unknown tool: {name}"
