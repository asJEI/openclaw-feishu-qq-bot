"""
技能注册表：LLM 为大脑，技能可插拔安装。

加载顺序：1) 内置 (web_search, recall_long_term_memory)
        2) pip 包 entry_points (openclaw_bot.skills)
        3) config skills.extra_modules 指定的模块
        4) src/skills/plugins/*.py 本地插件

插件约定：
- TOOL_DEFINITIONS: list，OpenAI function 格式
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
from typing import Any, Awaitable, Callable, Optional

from src.core.config import settings
from src.skills import builtin_tools

logger = logging.getLogger(__name__)

Runner = Callable[..., Awaitable[Optional[str]]]

_loaded = False
_merged_definitions: list[dict[str, Any]] = []
_runners: list[Runner] = []
_loaded_skill_names: list[str] = []


def _fn_name(defn: dict[str, Any]) -> str:
    return str(defn.get("function", {}).get("name", ""))


def _merge_tool_defs(*lists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for lst in lists:
        for d in lst:
            n = _fn_name(d)
            if n:
                merged[n] = d
    return list(merged.values())


def _load_entry_point_skills() -> list[Any]:
    """从 pip 包 entry_points 加载（需在 pyproject/setup.py 声明 openclaw_bot.skills）"""
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
                _loaded_skill_names.append(ep.name)
                logger.info("已加载技能包（entry_point）: %s", ep.name)
        except Exception as e:
            logger.warning("entry_point 技能加载失败 %s: %s", ep.name, e)
    return mods


def _load_extra_module_skills() -> list[Any]:
    """从 config skills.extra_modules 加载（支持 pip install 后配置模块路径）"""
    mods: list[Any] = []
    extra = settings.get("skills.extra_modules") or []
    if not isinstance(extra, list):
        return mods
    for mod_path in extra:
        if not mod_path or not isinstance(mod_path, str):
            continue
        try:
            mod = importlib.import_module(mod_path.strip())
            if hasattr(mod, "TOOL_DEFINITIONS") and hasattr(mod, "run_tool"):
                mods.append(mod)
                _loaded_skill_names.append(mod_path)
                logger.info("已加载技能包（extra_modules）: %s", mod_path)
        except Exception as e:
            logger.warning("extra_module 技能加载失败 %s: %s", mod_path, e)
    return mods


def _load_plugin_modules() -> list[Any]:
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
        stem = path.stem
        if stem in disabled:
            logger.info("已跳过技能插件（disable_plugins）: %s", stem)
            continue

        mod_name = f"_skill_plugin_{stem}"
        spec = importlib.util.spec_from_file_location(mod_name, path)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            logger.warning("技能插件加载失败 %s: %s", path, e)
            sys.modules.pop(mod_name, None)
            continue

        tools = getattr(mod, "TOOL_DEFINITIONS", None)
        runner = getattr(mod, "run_tool", None)
        if not tools or not callable(runner):
            logger.debug("跳过（无 TOOL_DEFINITIONS 或 run_tool）: %s", path)
            continue
        if not isinstance(tools, list):
            logger.warning("插件 TOOL_DEFINITIONS 须为 list: %s", path)
            continue

        mods.append(mod)
        _loaded_skill_names.append(stem)
        logger.info("已加载技能插件: %s", stem)

    return mods


def _ensure_loaded() -> None:
    global _loaded, _merged_definitions, _runners
    if _loaded:
        return
    _loaded = True

    all_mods: list[Any] = []
    all_mods.extend(_load_entry_point_skills())
    all_mods.extend(_load_extra_module_skills())
    all_mods.extend(_load_plugin_modules())

    def_lists = [builtin_tools.TOOL_DEFINITIONS] + [
        getattr(m, "TOOL_DEFINITIONS", []) for m in all_mods
    ]
    _merged_definitions = _merge_tool_defs(*def_lists)

    _runners = [m.run_tool for m in all_mods]
    _runners.append(builtin_tools.run_tool)


def get_tool_definitions() -> list[dict[str, Any]]:
    _ensure_loaded()
    return list(_merged_definitions)


def get_loaded_skill_summary() -> str:
    """返回已加载技能清单，用于启动日志"""
    _ensure_loaded()
    names = [_fn_name(d) for d in _merged_definitions]
    return ", ".join(names) if names else "(无)"


async def dispatch_tool(
    name: str,
    arguments_json: str,
    chat_id: str,
    vector_query_fn,
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
            logger.exception("技能执行异常: %s", name)
            return f"技能执行出错（{type(e).__name__}）: {e}"
        if out is not None:
            return out

    return f"未知工具: {name}"
