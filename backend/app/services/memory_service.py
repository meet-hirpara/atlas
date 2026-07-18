import os
import uuid
from typing import List
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from app.config import get_settings

settings = get_settings()


class MemoryService:
    def __init__(self):
        os.makedirs(settings.chroma_persist_dir, exist_ok=True)
        self.embeddings = MistralAIEmbeddings(
            model="mistral-embed",
            mistral_api_key=settings.mistral_api_key,
        )
        self.vectorstore = Chroma(
            collection_name="chat_memory",
            embedding_function=self.embeddings,
            persist_directory=settings.chroma_persist_dir,
        )

    def store_exchange(self, session_id: str, user_msg: str, assistant_msg: str):
        doc = Document(
            page_content=f"User: {user_msg}\nAssistant: {assistant_msg}",
            metadata={"session_id": session_id},
        )
        self.vectorstore.add_documents([doc])

    def recall_relevant(self, session_id: str, query: str, k: int = 4) -> List[str]:
        results = self.vectorstore.similarity_search(
            query,
            k=k,
            filter={"session_id": session_id},
        )
        return [doc.page_content for doc in results]

    def clear_session(self, session_id: str) -> None:
        try:
            self.vectorstore._collection.delete(where={"session_id": session_id})
        except Exception:
            pass


memory_service = MemoryService()
