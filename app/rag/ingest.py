import os
from typing import List, Optional
from langchain_core.documents import Document
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_core.embeddings import FakeEmbeddings
from app.core.config import settings
from app.core.logging import logger


import hashlib
import math
import re
from langchain_core.embeddings import Embeddings


STOPWORDS = {
    "what", "which", "who", "when", "where", "why", "how", "is", "are", "was", "were",
    "be", "been", "being", "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
    "for", "with", "about", "against", "between", "into", "through", "during", "before",
    "after", "above", "below", "from", "up", "down", "of", "off", "over", "under", "again",
    "further", "then", "once", "here", "there", "all", "any", "both", "each", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so",
    "than", "too", "very", "s", "t", "can", "will", "just", "don", "should", "now",
    "d", "ll", "m", "o", "re", "ve", "y", "do", "does", "did", "have", "has", "had",
    "our", "you", "your", "we", "us", "me", "i", "azure", "paradise", "resort"
}


class DeterministicKeywordEmbedding(Embeddings):
    """Deterministic hashing-based embedding ensuring offline keyword retrieval accuracy."""

    def __init__(self, dims: int = 1024):
        self.dims = dims

    def _embed(self, text: str) -> List[float]:
        vec = [0.0] * self.dims
        words = re.findall(r"\w+", text.lower())
        content_words = [w for w in words if w not in STOPWORDS and len(w) > 1]
        if not content_words:
            content_words = words
        if not content_words:
            return vec
        for w in content_words:
            h = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16) % self.dims
            vec[h] += 1.0
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text)


def get_embedding_model():
    """Returns OpenAI embeddings if API key is set, else DeterministicKeywordEmbedding."""
    if settings.OPENAI_API_KEY:
        try:
            from langchain_openai import OpenAIEmbeddings
            return OpenAIEmbeddings(openai_api_key=settings.OPENAI_API_KEY)
        except Exception as exc:
            logger.warning(f"Could not initialize OpenAIEmbeddings: {exc}. Using fallback.")
    return DeterministicKeywordEmbedding(dims=1024)


def load_and_split_documents(knowledge_dir: str = "./data/knowledge") -> List[Document]:
    """
    Loads all markdown knowledge documents and splits into semantic chunks
    using LangChain RecursiveCharacterTextSplitter.
    """
    if not os.path.exists(knowledge_dir):
        os.makedirs(knowledge_dir, exist_ok=True)

    loader = DirectoryLoader(
        path=knowledge_dir,
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"}
    )
    docs = loader.load()
    logger.info(f"Loaded {len(docs)} knowledge documents from {knowledge_dir}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=50,
        separators=["\n## ", "\n### ", "\n- ", "\n\n", "\n", " "]
    )
    split_docs = splitter.split_documents(docs)
    # Filter out empty or header-only chunks that lack substantive policy content
    filtered_docs = [d for d in split_docs if len(d.page_content.strip()) > 40]
    logger.info(f"Split documents into {len(filtered_docs)} substantive semantic chunks.")
    return filtered_docs


def build_vector_store(
    docs: Optional[List[Document]] = None,
    persist_dir: str = "./data/chroma_db"
) -> Chroma:
    """
    Builds or loads a LangChain Chroma vector store populated with resort knowledge.
    """
    if docs is None:
        docs = load_and_split_documents()

    embeddings = get_embedding_model()

    vector_store = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        collection_name="resort_knowledge"
    )
    logger.info(f"Built LangChain Chroma vector store with {len(docs)} documents.")
    return vector_store


if __name__ == "__main__":
    docs = load_and_split_documents()
    store = build_vector_store(docs)
    print(f"Vector store created successfully with {len(docs)} chunks.")
