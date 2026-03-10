"""Unit tests for RAG chunker and document loader."""

from pathlib import Path

import pytest

from app.rag.chunker import chunk_documents
from app.rag.document_loader import load_kb_documents

KB_DIR = Path(__file__).parent.parent.parent.parent / "knowledge_base" / "docs_internal"


@pytest.mark.skipif(not KB_DIR.exists(), reason="KB directory not available")
def test_load_documents():
    docs = list(load_kb_documents(KB_DIR))
    assert len(docs) > 0
    for doc in docs:
        assert doc.page_content
        assert "source" in doc.metadata


@pytest.mark.skipif(not KB_DIR.exists(), reason="KB directory not available")
def test_chunk_documents():
    docs = list(load_kb_documents(KB_DIR))
    chunks = chunk_documents(docs[:3])
    assert len(chunks) >= len(docs[:3])
    for chunk in chunks:
        assert len(chunk.page_content) <= 800
