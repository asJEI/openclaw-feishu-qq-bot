import uvicorn
import json
from fastapi import FastAPI, Request
from src.channels.feishu_handler import FeishuHandler
from src.core.config import settings
from src.core.logger import logger

app = FastAPI()
feishu_handler = FeishuHandler()

@app.get("/")
def index():
    return {"status": "running", "msg": "OpenClaw Feishu Bot is alive!"}

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

if __name__ == "__main__":
    # 获取端口，默认 8080
    port = settings.get("server.port", 8080)
    
    print("\n" + "🚀" * 20)
    print(f"项目尝试启动在端口: {port}")
    print(f"请确保你的 ngrok 转发的是: {port}")
    print("🚀" * 20 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=int(port))