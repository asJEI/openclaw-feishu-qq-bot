---
name: openclaw-feishu-qq-bot
description: >-
  维护本仓库中 OpenClaw 多通道机器人（飞书 Webhook、QQ 开放平台 Webhook）、
  工具调用与 Chroma 长期记忆时的约定与部署步骤。
---

# OpenClaw 飞书 + QQ 机器人项目

## 架构要点

- **飞书**：`POST /webhook/feishu`，事件 `im.message.receive_v1`，异步回复避免超时重试。
- **QQ**：`POST /webhook/qq`，载荷为网关结构 `op` / `d` / `t`。须校验 `X-Signature-Ed25519` + `X-Signature-Timestamp`（与 Body 拼接规则见 `src/channels\qq_crypto.py`）。`op=13` 为回调验证，需返回 `plain_token` + `signature`。
- **模型**：OpenAI 兼容 `POST {api_url}/chat/completions`；可开启 `tools`（`src/skills/tools.py`）。

## 记忆策略

- **短期**：`src/core/memory.py` 按 `memory.short_term_max_messages` 保留消息列表。
- **触发总结**：达到条数后由模型生成 Markdown「总结报告」，合并进滚动摘要，并调用 `vector_db.save_summary_report` 写入 Chroma。
- **可选**：`memory.store_each_turn_in_vector: true` 时每轮额外 `save_iteration`。
- **检索**：每次用户提问用当前句做 query，按 `chat_id` 过滤（飞书 `chat_id`、QQ 使用 `qq:c2c:` / `qq:group:` / `qq:guild:` 前缀）。

## 部署（Docker）

1. 复制 `config/config-example.yaml` 为 `config/config.yaml`，填写密钥。
2. 与 `docker-compose.yml` 同机部署时，将 `database.chroma_host` 设为 **`chromadb`**，`chroma_port` **8000**。
3. `docker compose up -d`。对外暴露 **8080** 供 ngrok/反代指向飞书与 QQ Webhook。
4. QQ 控制台回调 URL 形如 `https://你的域名/webhook/qq`（须 HTTPS，端口限制见 QQ 文档）。

## 可插拔 Skills（LLM 大脑 + 技能）

- 注册表：`src/skills/registry.py` 按序加载 **内置** → **pip entry_points**（`openclaw_bot.skills`）→ **skills.extra_modules** → **plugins/*.py**。
- 插件约定：导出 `TOOL_DEFINITIONS` 与 `async def run_tool(name, args, *, chat_id, vector_query_fn) -> str | None`；不处理的 `name` 返回 `None`。
- 详细开发指南：`docs/SKILL_DEVELOPMENT.md`。示例：`src/skills/plugins/example_time.py`。

## 修改代码时的检查清单

- 新增通道：复用 `agent.get_response(chat_id, text)`，保证 `chat_id` 稳定且唯一。
- 新增内置工具：改 `src/skills/builtin_tools.py`；新增第三方式能力：优先加插件文件。
- 勿在仓库中提交真实 `config.yaml` 或带密钥的示例。
