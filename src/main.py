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
    return {"status": "running", "msg": "NewAPI Feishu + QQ Bot is alive!"}

# 飞书回调地址
@app.post("/webhook/feishu")
async def feishu_webhook(request: Request):
    try:
        data = await request.json()
    except Exception as e:
        logger.error("解析飞书 JSON 失败: %s", e)
        return {"code": 1, "msg": "invalid json"}

    if settings.get("server.debug"):
        logger.info("收到飞书回调: %s", json.dumps(data, ensure_ascii=False))

    if data.get("type") == "url_verification":
        logger.info("飞书 URL 验证 (Challenge)")
        return {"challenge": data.get("challenge")}

    try:
        result = await feishu_handler.handle_event(data)
        return result
    except Exception as e:
        logger.exception("飞书 Handler 处理报错")
        return {"code": 1, "msg": str(e)}


@app.post("/webhook/qq")
async def qq_webhook(request: Request):
    raw_body = await request.body()
    headers = {k: v for k, v in request.headers.items()}
    return await qq_handler.handle_raw_webhook(headers, raw_body)


if __name__ == "__main__":
    # 获取端口，默认 8080
    port = settings.get("server.port", 8080)
    
    logger.info("Server listening on 0.0.0.0:%s (point ngrok / reverse proxy here)", port)
    
    uvicorn.run(app, host="0.0.0.0", port=int(port))