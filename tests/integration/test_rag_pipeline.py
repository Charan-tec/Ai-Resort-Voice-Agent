import pytest
from app.rag.ingest import load_and_split_documents, build_vector_store
from app.rag.retriever import ResortRAGRetriever


def test_rag_ingest_and_split():
    docs = load_and_split_documents("./data/knowledge")
    assert len(docs) > 0
    # Verify metadata and content
    first = docs[0]
    assert hasattr(first, "page_content")
    assert hasattr(first, "metadata")
    assert "source" in first.metadata


def test_rag_retrieval():
    docs = load_and_split_documents("./data/knowledge")
    vector_store = build_vector_store(docs)
    retriever = ResortRAGRetriever(vector_store=vector_store, top_k=2)

    results = retriever.retrieve("What time is check in and check out?")
    assert len(results) > 0
    contents = " ".join([d.page_content for d in results]).lower()
    assert "check-in" in contents or "check-out" in contents or "3:00 pm" in contents or "11:00 am" in contents
