# OpenClaw多平台个人AI智能体

个人项目 | 2026.03-至今 

基于开源OpenClaw框架二次开发的24h在线多平台个人AI智能体，已实现飞书 + QQ 跨平台消息路由、自动回复、日报生成、信息抓取等功能。

### 项目亮点
- 支持飞书自建应用+Tencent Bot SDK 双平台同时在线
- 实现 Function Calling / Tool Calling（自动调用外部接口）
- 集成持久化内存+Docker 部署
- 已验证 RAG+提示工程能力（后续将升级 LangGraph 多智能体）

### 核心功能
1. 飞书/QQ自动回复（支持@机器人指令）
2. 每日日报自动生成并推送
3. 信息抓取+总结（飞书消息/QQ消息）
4. Tool Calling 示例（天气查询、时间提醒、数据库查询等）

### 技术栈
- **后端**：Python+FastAPI
- **Agent 框架**：OpenClaw
- **部署**：Docker+阿里云轻量服务器
- **集成**：Feishu OpenAPI+Tencent Bot SDK
- **模型**：本地 Ollama Qwen3.5-9B（4bit量化）/Qwen3.5
- **计划升级**：LangGraph + MCP 多智能体

### 部署步骤
# 1. 克隆仓库
git clone https://github.com/asJEI/openclaw-feishu-qq-bot.git
# 2. 启动 Docker
docker-compose up -d
# 3. 配置飞书/QQ密钥（config/config.yaml）
# 4. 访问 http://47.81.33.163:8080 测试

### 运行成果
# 1.保证24h稳定运行
# 2.每日准时发送前日总结以及知识点推送
# 3.节省手动操作时间

### 项目截图


