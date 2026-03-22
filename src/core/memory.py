from src.core.config import settings
from src.core.vector_memory import vector_db


class Memory:
    def __init__(self):
        self.data = {}
        self.summaries = {}
        self.max_len = int(settings.get("memory.short_term_max_messages", 6))

    def get_context(self, chat_id):
        history = self.data.get(chat_id, [])
        summary = self.summaries.get(chat_id, "")
        return summary, history

    def add_message(self, chat_id, role, content):
        if chat_id not in self.data:
            self.data[chat_id] = []
        self.data[chat_id].append({"role": role, "content": content})

    async def try_summarize(self, chat_id, agent_instance):
        history = self.data.get(chat_id, [])
        if len(history) < self.max_len:
            return

        print(f"📝 [Memory] 对话达到 {self.max_len} 条消息，生成总结报告并写入向量库...")

        prompt = (
            "你是对话归档助手。请阅读以下多轮对话，输出一份简短的「总结报告」，"
            "使用 Markdown 小标题分节，至少包含：\n"
            "1) 用户画像与偏好\n"
            "2) 已确认的事实与约定\n"
            "3) 未解决问题 / 待跟进\n"
            "要求：客观、可检索、不要复述逐句对话。\n\n"
            "对话内容：\n"
        )
        for msg in history:
            prompt += f"{msg['role']}: {msg['content']}\n"

        report = await agent_instance.get_simple_chat(prompt)
        if not report:
            return

        old = self.summaries.get(chat_id, "")
        self.summaries[chat_id] = f"{old}\n\n---\n\n{report}".strip() if old else report

        vector_db.save_summary_report(chat_id, report)

        self.data[chat_id] = history[-2:]
        print(f"✨ [Memory] 总结已更新，短期记忆已压缩保留最近 1 轮")


memory = Memory()
