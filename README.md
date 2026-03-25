# Feishu QQ LLM Bot

飞书 + QQ 双平台 AI 机器人，基于 OpenAI 兼容 API 实现多轮对话、工具调用与长期记忆。

## 特性

- **双平台接入**：飞书 Lark、QQ 开放平台 Webhook
- **模型兼容**：支持任何 OpenAI 兼容接口（NewAPI、OneAPI、直接调用等）
- **工具调用**：联网搜索、长期记忆检索，支持自定义插件
- **记忆系统**：短期窗口 + Chroma 向量长期记忆
- **异步架构**：FastAPI + asyncio，高并发处理

## 技术栈

| 组件 | 用途 |
|------|------|
| FastAPI | Web 框架、Webhook 接收 |
| httpx | 异步 HTTP 客户端 |
| ChromaDB | 向量存储、语义检索 |
| PyYAML | 配置管理 |

## 目录结构

```
.
├── config/
│   └── config-example.yaml     # 配置模板
├── src/
│   ├── channels/               # 平台适配层
│   │   ├── feishu_handler.py     # 飞书消息处理
│   │   ├── feishu_crypto.py    # 飞书加密验证
│   │   ├── qq_handler.py       # QQ 消息处理
│   │   └── qq_crypto.py        # QQ Ed25519 验签
│   ├── core/                   # 核心逻辑
│   │   ├── agent.py            # AI 对话管理
│   │   ├── config.py           # 配置读取
│   │   ├── logger.py           # 日志配置
│   │   ├── memory.py           # 短期记忆
│   │   └── vector_memory.py    # 向量记忆
│   ├── skills/                 # 技能系统
│   │   ├── builtin_tools.py    # 内置工具
│   │   ├── registry.py         # 技能注册表
│   │   ├── tools.py            # 工具执行器
│   │   └── plugins/            # 插件目录
│   └── main.py                 # 入口
├── docker-compose.yml          # 一键部署
└── requirements.txt            # 依赖
```

## 快速开始

### 本地运行

```bash
# 1. 克隆仓库
git clone <仓库地址>.git
cd feishu-qq-llm-bot

# 2. 创建环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 复制并编辑配置
cp config/config-example.yaml config/config.yaml
# 编辑 config.yaml 填入 feishu/qq/openclaw 等信息

# 5. 启动
python src/main.py
```

服务监听 `http://0.0.0.0:8080`，测试访问：

```bash
curl http://localhost:8080/
# {"status":"running",...}
```

### Docker 部署

```bash
# 1. 准备配置
cp config/config-example.yaml config/config.yaml
# 编辑：database.chroma_host 改为 chromadb（Compose 服务名）

# 2. 启动
docker compose up -d

# 3. 查看日志
docker compose logs -f bot
```

## 配置说明

完整配置模板见 `config/config-example.yaml`，必填项：

| 配置段 | 关键字段 | 说明 |
|--------|----------|------|
| `feishu` | `app_id`, `app_secret` | 飞书自建应用凭证 |
| `qq` | `app_id`, `client_secret` | QQ 机器人控制台获取 |
| `openclaw` | `api_url`, `api_key`, `model` | LLM 接口地址与密钥 |
| `database` | `chroma_host`, `chroma_port` | 向量库连接，可选 |

### 最小可运行配置

```yaml
server:
  port: 8080
  debug: false

feishu:
  app_id: "cli_xxxxx"
  app_secret: "xxxxxxxx"

qq:
  app_id: "1234567890"
  client_secret: "xxxxxxxx"

openclaw:
  api_url: "https://api.openai.com/v1"
  api_key: "sk-xxxxxxxx"
  model: "gpt-4o-mini"
  enable_tools: true

memory:
  short_term_max_messages: 6
```

## 平台接入

### 飞书配置

1. 前往[飞书开放平台](https://open.feishu.cn/)创建企业自建应用
2. 开启权限：`im:chat:readonly`, `im:message:send`, `im:message.group_msg`
3. 事件订阅地址：`https://你的域名/webhook/feishu`
4. 订阅事件：`im.message.receive_v1`

### QQ 配置

1. 前往[QQ 开放平台](https://bot.q.qq.com/)注册机器人
2. 纯 Webhook 模式，回调地址：`https://你的域名/webhook/qq`
3. 本地开发使用 ngrok 暴露 HTTPS：

```bash
ngrok http 8080
# 获得 https://xxxx.ngrok-free.app
# 填入 QQ 控制台回调地址: https://xxxx.ngrok-free.app/webhook/qq
```

## 开发技能

在 `src/skills/plugins/` 创建 `my_skill.py`：

```python
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"}
                },
                "required": ["city"]
            }
        }
    }
]

async def run_tool(name, args, *, chat_id, vector_query_fn):
    if name != "get_weather":
        return None
    city = args.get("city")
    return f"{city} 今天晴，25°C"
```

重启服务即可生效。详细见 [SKILL_DEVELOPMENT.md](docs/SKILL_DEVELOPMENT.md)。

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 健康检查 |
| POST | `/webhook/feishu` | 飞书事件订阅 |
| POST | `/webhook/qq` | QQ Webhook |

## 常见问题

**Q: 飞书收到消息但无回复？**
- 检查 `config.yaml` 中 `feishu.app_id/app_secret` 是否正确
- 查看日志确认是否收到请求：`docker compose logs -f bot`
- 确认权限已开通并发布版本

**Q: QQ Webhook 验签失败？**
- 确认 `qq.client_secret` 与控制台一致
- 生产环境确保 `qq.verify_signature: true`

**Q: 长期记忆不生效？**
- ChromaDB 未连接时自动降级，检查日志是否有连接错误
- 或设置 `memory.store_each_turn_in_vector: true` 强制写入

**Q: 模型返回"工具调用次数过多"？**
- 调大 `openclaw.max_tool_rounds`（默认 5）
- 或简化问题，减少工具依赖

## License

MIT
