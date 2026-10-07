from typing import List, Optional
from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma
from app.core.config import settings
from app.core.logging import logger
from app.rag.ingest import build_vector_store


class ResortRAGRetriever:
    """
    Production LangChain Retriever for resort knowledge base.
    Returns metadata-rich Document objects.
    """

    def __init__(self, vector_store: Optional[Chroma] = None, top_k: int = 3):
        self.top_k = top_k
        self._vector_store = vector_store

    def _ensure_vector_store(self):
        if self._vector_store is None:
            self._vector_store = build_vector_store()

    def retrieve(self, query: str, top_k: Optional[int] = None) -> List[Document]:
        """Query vector store using LangChain similarity search with relevance score."""
        self._ensure_vector_store()
        k = top_k or self.top_k

        results: List[Document] = self._vector_store.similarity_search(query, k=k)
        logger.info(f"Retrieved {len(results)} LangChain Document objects for query: '{query}'")
        return results

    async def aretrieve(self, query: str, top_k: Optional[int] = None) -> List[Document]:
        """Asynchronous retrieval interface."""
        return self.retrieve(query, top_k=top_k)


_global_retriever: Optional[ResortRAGRetriever] = None


def get_retriever() -> ResortRAGRetriever:
    """Singleton getter for resort RAG retriever."""
    global _global_retriever
    if _global_retriever is None:
        _global_retriever = ResortRAGRetriever(top_k=settings.RAG_TOP_K)
    return _global_retriever
