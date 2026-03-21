import json
from src.core.config import settings

class Memory:
    def __init__(self, max_len=6):
        self.data = {}  # 短期记忆：{ chat_id: [messages] }
        self.summaries = {}  # 长期摘要：{ chat_id: "用户叫小明，喜欢写Python..." }
        self.max_len = max_len

    def get_context(self, chat_id):
        """获取带摘要的完整上下文"""
        history = self.data.get(chat_id, [])
        summary = self.summaries.get(chat_id, "")
        return summary, history

    async def try_summarize(self, chat_id, agent_instance):
        """如果对话太长，触发 AI 摘要提炼"""
        history = self.data.get(chat_id, [])
        if len(history) >= self.max_len:
            print(f"📝 [Memory] 对话达到 {self.max_len} 轮，开始提炼关键信息...")
            
            # 构造提炼 Prompt
            prompt = (
                "请根据以下对话，提炼关于用户的核心画像（如姓名、偏好、职业、提到的重要事实）。"
                "请用简短的陈述句总结，不要废话。对话内容如下：\n"
            )
            for msg in history:
                prompt += f"{msg['role']}: {msg['content']}\n"
            
            # 调用 Agent 进行总结 (这里可以调一个更便宜的模型)
            summary = await agent_instance.get_simple_chat(prompt)
            
            # 更新长期摘要
            old_summary = self.summaries.get(chat_id, "")
            self.summaries[chat_id] = f"{old_summary} {summary}".strip()
            
            # 清空短期记忆，只保留最后一轮
            self.data[chat_id] = history[-2:]
            print(f"✨ [Memory] 摘要更新完成: {self.summaries[chat_id]}")

    def add_message(self, chat_id, role, content):
        if chat_id not in self.data:
            self.data[chat_id] = []
        self.data[chat_id].append({"role": role, "content": content})

memory = Memory()