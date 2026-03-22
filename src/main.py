import json
import sys
from pathlib import Path

# 允许直接执行 `python src/main.py`（无需在 PowerShell 里单独设 PYTHONPATH）
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import uvicorn
from fastapi import FastAPI, Request
from src.channels.feishu_handler import FeishuHandler
from src.channels.qq_handler import QQBotHandler
from src.core.config import settings
from src.core.logger import logger

app = FastAPI()
feishu_handler = FeishuHandler()
qq_handler = QQBotHandler()

@app.get("/")
def index():
    return {"status": "running", "msg": "OpenClaw Feishu + QQ Bot is alive!"}

# 飞书回调地址
@app.post("/webhook/feishu")
async def feishu_webhook(request: Request):
    # 1. 获取原始 JSON 数据
    try:
        data = await request.json()
    except Exception as e:
        print(f"❌ 解析 JSON 失败: {e}")
        return {"code": 1, "msg": "invalid json"}

    # 2. 打印醒目的调试日志（手术灯开启）
    print("\n" + "⭐" * 50)
    print("📢 [收到飞书回调请求]")
    print(f"数据内容: {json.dumps(data, indent=2, ensure_ascii=False)}")
    print("⭐" * 50 + "\n")

    # 3. 验证是否是飞书的 URL 验证请求 (Challenge)
    if data.get("type") == "url_verification":
        print("🔗 正在响应飞书 URL 验证 (Challenge)...")
        return {"challenge": data.get("challenge")}

    # 4. 交给 FeishuHandler 处理业务逻辑
    try:
        result = await feishu_handler.handle_event(data)
        return result
    except Exception as e:
        print(f"💥 Handler 处理报错: {e}")
        return {"code": 1, "msg": str(e)}


@app.post("/webhook/qq")
async def qq_webhook(request: Request):
    raw_body = await request.body()
    headers = {k: v for k, v in request.headers.items()}
    return await qq_handler.handle_raw_webhook(headers, raw_body)


if __name__ == "__main__":
    # 获取端口，默认 8080
    port = settings.get("server.port", 8080)
    
    print(f"\n[Server] listening on 0.0.0.0:{port} (point ngrok / reverse proxy here)\n")
    
    uvicorn.run(app, host="0.0.0.0", port=int(port))