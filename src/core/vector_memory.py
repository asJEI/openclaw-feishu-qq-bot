import logging
import time

from src.core.config import settings

logger = logging.getLogger(__name__)


class VectorMemory:
    def __init__(self):
        self.host = settings.get("database.chroma_host", "127.0.0.1")
        self.port = int(settings.get("database.chroma_port", 8000))
        self._collection = None
        self._disabled = False
        self._client = None

    def _connect(self) -> bool:
        if self._disabled:
            return False
        if self._collection is not None:
            return True
        try:
            import chromadb

            self._client = chromadb.HttpClient(host=self.host, port=self.port)
            self._collection = self._client.get_or_create_collection(name="long_term_memory")
            logger.info("ChromaDB 已连接 %s:%s", self.host, self.port)
            return True
        except Exception as e:
            logger.warning("ChromaDB 不可用，长期记忆将降级为空: %s", e)
            self._disabled = True
            return False

    def save_summary_report(self, chat_id: str, report_text: str) -> None:
        if not report_text or not self._connect():
            return
        doc_id = f"sum_{chat_id}_{int(time.time() * 1000)}"
        self._collection.add(
            ids=[doc_id],
            documents=[report_text],
            metadatas=[{"chat_id": str(chat_id), "kind": "summary", "ts": time.time()}],
        )
        print(f"✅ [VectorDB] 已写入会话总结: {doc_id}")

    def save_iteration(self, chat_id: str, user_text: str, ai_reply: str) -> None:
        if not self._connect():
            return
        doc_content = f"User: {user_text}\nAssistant: {ai_reply}"
        doc_id = f"turn_{chat_id}_{int(time.time() * 1000)}"
        self._collection.add(
            ids=[doc_id],
            documents=[doc_content],
            metadatas=[{"chat_id": str(chat_id), "kind": "turn", "ts": time.time()}],
        )
        print(f"✅ [VectorDB] 已写入单轮对话: {doc_id}")

    def query_context(self, chat_id: str, query_text: str, n_results: int = 4) -> str:
        if not query_text or not self._connect():
            return ""
        try:
            results = self._collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where={"chat_id": str(chat_id)},
            )
            docs = results.get("documents", [[]])[0]
            return "\n---\n".join(docs) if docs else ""
        except Exception as e:
            logger.warning("向量检索失败: %s", e)
            return ""


vector_db = VectorMemory()
