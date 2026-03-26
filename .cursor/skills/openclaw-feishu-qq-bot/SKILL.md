---
name: openclaw-feishu-qq-bot
description: >-
  维护本仓库中基于 NewAPI 的多通道 AI Agent（飞书 Webhook、QQ 开放平台 Webhook）、
  工具调用与 Chroma 长期记忆时的约定与部署步骤。
---

# 基于 NewAPI 的多平台 AI Agent

## 架构要点

### 飞书通道
- 端点：`POST /webhook/feishu`
- 事件类型：`im.message.receive_v1`
- 注意：使用异步回复，避免超时重试

### QQ 通道
- 端点：`POST /webhook/qq`
- 载荷结构：网关格式 `op` / `d` / `t`
- 安全校验：`X-Signature-Ed25519` + `X-Signature-Timestamp`（Body 拼接规则见 `src/channels/qq_crypto.py`）
- 回调验证：`op=13` 时需返回 `plain_token` + `signature`

### 模型调用
- OpenAI 兼容格式：`POST {api_url}/chat/completions`
- 工具调用：通过 `src/skills/tools.py` 开启

## 记忆策略

| 类型 | 机制 | 配置 |
|------|------|------|
| 短期记忆 | 按 `memory.short_term_max_messages` 保留消息列表 | `src/core/memory.py` |
| 长期记忆 | 触发总结后生成 Markdown 报告，存入 Chroma | `vector_db.save_summary_report` |
| 逐轮存储 | 可选，每轮额外保存 | `memory.store_each_turn_in_vector: true` |
| 检索 | 用当前句子做 query，按 `chat_id` 过滤 | 飞书用 `chat_id`，QQ 用 `qq:c2c:` / `qq:group:` / `qq:guild:` 前缀 |

## Docker 部署

1. **配置**：复制 `config/config-example.yaml` → `config/config.yaml`，填入密钥
2. **Chroma 连接**：同机部署时，`database.chroma_host` 设为 `chromadb`，端口 `8000`
3. **启动**：`docker compose up -d`，对外暴露 `8080` 供 ngrok/反代使用
4. **QQ 回调**：URL 格式 `https://你的域名/webhook/qq`（须 HTTPS）

## 可插拔 Skills

加载顺序（`src/skills/registry.py`）：
1. 内置技能
2. pip 包 entry_points（`openclaw_bot.skills`）
3. `skills.extra_modules` 配置项
4. `plugins/*.py` 本地插件

### 插件开发约定

导出两个对象：
- `TOOL_DEFINITIONS`：OpenAI function calling 格式
- `run_tool(name, args, *, chat_id, vector_query_fn)`：只处理本技能的工具名，其他返回 `None`

详细指南见 `docs/SKILL_DEVELOPMENT.md`，示例参考 `src/skills/plugins/example_time.py`。

## 代码修改检查清单

- [ ] 新增通道：复用 `agent.get_response(chat_id, text)`，确保 `chat_id` 稳定唯一
- [ ] 新增内置工具：修改 `src/skills/builtin_tools.py`
- [ ] 新增第三方能力：优先添加插件文件
- [ ] 安全：勿在仓库中提交含真实密钥的 `config.yaml`
