import logging
import httpx
import json
import asyncio
from src.core.config import settings
from src.core.memory import memory  # 确保你已经建立了 memory.py

logger = logging.getLogger(__name__)

class Agent:
    def __init__(self):
        # 从 config.yaml 获取地址和令牌
        self.api_url = settings.get("openclaw.api_url", "").rstrip('/')
        self.api_key = settings.get("openclaw.api_key")
        print(f"✅ [Agent] 初始化成功，地址: {self.api_url}")

    async def get_simple_chat(self, prompt):
        """
        用于系统内部逻辑（如提炼摘要）的简单调用，不带上下文记忆
        """
        url = f"{self.api_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                result = response.json()
                return result['choices'][0]['message']['content']
        except Exception as e:
            print(f"❌ [Internal] 简单对话请求失败: {e}")
            return ""

    async def get_response(self, chat_id, user_text):
        """
        调用 DeepSeek 获取回复，并结合长期摘要与短期记忆
        """
        if not self.api_url or not self.api_key:
            return "错误：未配置 AI 接口地址或密钥，请检查 config.yaml"

        # 1. 从 memory 模块获取当前用户的：长期摘要 + 短期对话记录
        summary, history = memory.get_context(chat_id)
        
        # 2. 构造 System Prompt，注入长期记忆
        system_content = "你是一个实用的 AI 助手。"
        if summary:
            system_content += f"\n【关于用户的已知信息】：{summary}"
            
        messages = [{"role": "system", "content": system_content}]
        
        # 3. 拼接短期历史和当前问题
        messages.extend(history)
        messages.append({"role": "user", "content": user_text})

        url = f"{self.api_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "deepseek-chat", 
            "messages": messages,
            "stream": False
        }

        print(f"🧠 AI 思考中... (用户ID: {chat_id}, 历史轮数: {len(history)})")
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                
                if response.status_code != 200:
                    print(f"❌ AI 接口返回异常: {response.text}")
                    return f"AI 暂时不在线 (Error: {response.status_code})"
                
                result = response.json()
                content = result['choices'][0]['message']['content']
                print(f"✅ AI 响应成功")

                # 4. 【核心步骤】更新记忆
                # 存入短期记忆
                memory.add_message(chat_id, "user", user_text)
                memory.add_message(chat_id, "assistant", content)
                
                # 异步触发摘要提炼逻辑（不阻塞当前回复）
                asyncio.create_task(memory.try_summarize(chat_id, self))

                return content
                    
        except Exception as e:
            print(f"🔥 Agent 运行崩溃: {e}")
            return "我的大脑连接线断了..."

agent = Agent()