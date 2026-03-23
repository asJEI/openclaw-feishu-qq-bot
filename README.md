# Feishu QQ LLM Bot（飞书 + QQ 多通道 AI 机器人）

基于 **NewAPI**（OpenAI 兼容网关）的多通道 LLM 机器人：飞书（Lark）Webhook、QQ 开放平台 Webhook；通过 `chat/completions` 调用大模型，支持 **Function Calling**、**可插拔 Skills**、**短期记忆 + Chroma 长期向量记忆**。

> 配置中的 `openclaw` 段即 NewAPI / LLM 网关配置（`api_url`、`api_key`、`model` 等）。

---

## 功能概览

| 能力 | 说明                                                                |
| ---- | ------------------------------------------------------------------- |
| 飞书 | `POST /webhook/feishu`，异步回复、租户 token                        |
| QQ   | `POST /webhook/qq`，Ed25519 验签、`op=13` 回调验证、单聊/群@/频道 @ |
| 模型 | 多轮 tool_calls、内置联网搜索（ddgs）、长期记忆检索                 |
| 记忆 | 短期窗口 + 达轮数后总结写入 Chroma                                  |
| 扩展 | `src/skills/plugins/*.py` 插件式技能                                |

---

## 环境要求

- **Python 3.10+**（Docker 镜像为 3.11）
- 可访问的 **OpenAI 兼容 API**（`base_url` + `api_key`）
- 可选：**ChromaDB**（不配或连不上时长期记忆降级为空，服务仍可启动）

---

### 方式一：本机直接运行（适合调试）

```bash
git clone <你的仓库地址>.git
cd feishu-qq-llm-bot

python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate

pip install -r requirements.txt

cp config/config-example.yaml config/config.yaml
# 编辑 config/config.yaml：feishu / qq / openclaw / database / skills

python src/main.py
```

浏览器访问：`http://127.0.0.1:8080/`（端口见 `config.yaml` 里 `server.port`）。

**PowerShell 复制配置示例：**

```powershell
Copy-Item config\config-example.yaml config\config.yaml
```

### 方式二：Docker Compose

1. 同上复制并编辑好 **`config/config.yaml`**（不要提交到 Git）。
2. 在 `config.yaml` 中将向量库地址改为 Compose 服务名：

```yaml
database:
  chroma_host: chromadb
  chroma_port: 8000
```

3. 在项目根目录执行：

```bash
docker compose up -d --build
```

- 机器人：`http://<宿主机>:8080`
- Chroma：宿主机 `8000`（可按需改 `docker-compose.yml` 端口映射）

查看日志：`docker compose logs -f bot`

---

## 回调地址怎么填

| 平台          | URL 示例                                                                                                                                                  |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 飞书 事件订阅 | `https://你的域名/webhook/feishu`                                                                                                                         |
| QQ Webhook    | `https://你的域名/webhook/qq`（须 HTTPS，端口限制见 [QQ 文档](https://bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/event-emit.html)） |

本地开发可用 **ngrok** 等把本机 `8080` 暴露为 HTTPS。

---

## 更多文档

- [技能开发指南](docs/SKILL_DEVELOPMENT.md)：如何编写插件式技能、接入 pip 包

---
