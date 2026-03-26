# 技能开发指南

本项目采用 **LLM + 可插拔技能** 架构，通过 NewAPI 等 OpenAI 兼容网关调用大模型。技能可独立安装，无需改动核心代码。

## 技能加载顺序

1. **内置技能**：`web_search`（联网搜索）、`recall_long_term_memory`（长期记忆检索）
2. **pip 包**：声明 `openclaw_bot.skills` entry_point 的已安装包
3. **配置模块**：`skills.extra_modules` 中指定的模块路径
4. **本地插件**：`src/skills/plugins/*.py`

## 开发方式

### 方式一：本地插件（推荐入门）

在 `src/skills/plugins/` 下新建 `.py` 文件：

```python
"""示例：自定义技能"""

from typing import Any

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "my_custom_tool",
            "description": "简要描述工具用途，供 LLM 判断何时调用",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {"type": "string", "description": "参数说明"},
                },
                "required": ["param1"],
            },
        },
    }
]


async def run_tool(
    name: str,
    args: dict,
    *,
    chat_id: str,
    vector_query_fn,
) -> str | None:
    if name != "my_custom_tool":
        return None
    # 实现逻辑，可用 vector_query_fn(chat_id, query) 检索长期记忆
    return f"结果: {args.get('param1', '')}"
```

重启服务后 LLM 自动获得新工具。

### 方式二：pip 可安装包

适合团队共享或发布到 PyPI。

**目录结构：**
```
my-openclaw-skill/
├── pyproject.toml
├── src/
│   └── my_openclaw_skill/
│       └── __init__.py   # 包含 TOOL_DEFINITIONS 和 run_tool
```

**声明 entry_point：**
```toml
[project.entry-points."openclaw_bot.skills"]
my_skill = "my_openclaw_skill"
```

**安装：**
```bash
pip install ./my-openclaw-skill
# 或 pip install my-openclaw-skill  # 若已发布 PyPI
```

### 方式三：extra_modules 配置

技能包已安装但未声明 entry_point 时，在 `config.yaml` 中添加：

```yaml
skills:
  extra_modules: ["my_package.skill_module"]
```

## 技能接口规范

| 字段 | 类型 | 说明 |
|------|------|------|
| `TOOL_DEFINITIONS` | `list[dict]` | OpenAI function calling 格式 |
| `run_tool` | `async (name, args, *, chat_id, vector_query_fn) -> str \| None` | 只处理本技能的工具，其他返回 `None` |

**`vector_query_fn(chat_id, query)`** —— 检索该会话的长期记忆，返回语义相关的历史文本。

## 禁用技能

- **禁用指定插件**：`skills.disable_plugins: ["example_time"]`
- **关闭所有插件**：`skills.enable_plugins: false`（内置 `web_search`、`recall` 仍可用）
