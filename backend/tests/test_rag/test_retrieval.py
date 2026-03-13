"""Unit tests for RAG chunker, document loader, and HybridRetriever logic."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.documents import Document

from app.rag.chunker import chunk_documents
from app.rag.document_loader import load_kb_documents
from app.rag.hybrid_retriever import (
    HybridRetriever,
    _apply_corpus_filter,
    _matches_topic,
    _rrf,
)

KB_DIR = Path(__file__).parent.parent.parent.parent / "knowledge_base" / "docs_internal"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _doc(doc_id: str, content: str = "text", route_keys=None) -> Document:
    metadata: dict = {"doc_id": doc_id}
    if route_keys is not None:
        metadata["route_keys"] = route_keys
    return Document(page_content=content, metadata=metadata)


def _mock_retriever(corpus: str, docs: list[Document]) -> HybridRetriever:
    """Build a HybridRetriever with mocked vector store and BM25."""
    mock_vs = AsyncMock()
    mock_vs.asimilarity_search = AsyncMock(return_value=docs)
    mock_bm25 = MagicMock()
    mock_bm25.retrieve = MagicMock(return_value=docs)
    return HybridRetriever(mock_vs, mock_bm25, corpus)


# ---------------------------------------------------------------------------
# Existing integration tests (guarded by KB directory presence)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# _rrf unit tests
# ---------------------------------------------------------------------------


def test_rrf_deduplicates_and_orders():
    """A document appearing in both lists scores higher and appears only once."""
    doc_a = _doc("L2.TOPIC.A", "content A")
    doc_b = _doc("L2.TOPIC.B", "content B")
    doc_c = _doc("L2.TOPIC.C", "content C")

    list1 = [doc_a, doc_b]
    list2 = [doc_b, doc_c]  # doc_b is in both → highest RRF score

    result = _rrf([list1, list2])

    ids = [d.metadata["doc_id"] for d in result]
    assert len(ids) == len(set(ids)), "Duplicate documents found in RRF output"
    assert ids[0] == "L2.TOPIC.B", "doc_b should rank first (appears in both lists)"


def test_rrf_single_list():
    """RRF over a single list preserves original order."""
    docs = [_doc(f"L2.TOPIC.{i}", f"content {i}") for i in range(3)]
    result = _rrf([docs])
    assert [d.metadata["doc_id"] for d in result] == [d.metadata["doc_id"] for d in docs]


# ---------------------------------------------------------------------------
# _apply_corpus_filter unit tests
# ---------------------------------------------------------------------------


def test_apply_corpus_filter_prefix():
    """procedure corpus only allows L2.TOPIC.*, L1.*, and L0.* prefixes."""
    docs = [
        _doc("L2.TOPIC.001", "procedure doc"),
        _doc("L2.SUPPORT.RULE.001", "rule doc"),
        _doc("L1.OVERVIEW.001", "L1 doc"),
        _doc("L0.INTRO", "L0 doc"),
    ]
    result = _apply_corpus_filter(docs, "procedure")
    ids = {d.metadata["doc_id"] for d in result}
    assert "L2.TOPIC.001" in ids
    assert "L1.OVERVIEW.001" in ids
    assert "L0.INTRO" in ids
    assert "L2.SUPPORT.RULE.001" not in ids


def test_apply_corpus_filter_rule():
    """rule corpus allows L2.SUPPORT.RULE.* and L0.* prefixes."""
    docs = [
        _doc("L2.SUPPORT.RULE.001", "rule doc"),
        _doc("L2.TOPIC.001", "topic doc"),
        _doc("L0.INTRO", "L0 doc"),
    ]
    result = _apply_corpus_filter(docs, "rule")
    ids = {d.metadata["doc_id"] for d in result}
    assert "L2.SUPPORT.RULE.001" in ids
    assert "L0.INTRO" in ids
    assert "L2.TOPIC.001" not in ids


# ---------------------------------------------------------------------------
# _matches_topic unit tests
# ---------------------------------------------------------------------------


def test_matches_topic_vibration():
    """A doc tagged vibration_swing matches that topic and no other."""
    doc = _doc("D1", route_keys=["vibration_swing"])
    assert _matches_topic(doc, "vibration_swing") is True
    assert _matches_topic(doc, "governor_oil_pressure") is False


def test_matches_topic_string_serialized():
    """ChromaDB may serialize lists as comma-separated strings — handle both."""
    doc = _doc("D2", route_keys="vibration_swing, bearing_temp_cooling")
    assert _matches_topic(doc, "vibration_swing") is True
    assert _matches_topic(doc, "bearing_temp_cooling") is True
    assert _matches_topic(doc, "governor_oil_pressure") is False


def test_matches_topic_no_route_keys():
    """Docs without route_keys metadata return False for any topic filter."""
    doc = _doc("D3")
    assert _matches_topic(doc, "vibration_swing") is False


# ---------------------------------------------------------------------------
# HybridRetriever.aretrieve async tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aretrieve_returns_top_k():
    """aretrieve returns at most reranker_top_k results from the fused set."""
    from app.config import settings

    procedure_docs = [
        _doc(f"L2.TOPIC.{i:03d}", f"content {i}") for i in range(5)
    ]
    retriever = _mock_retriever("procedure", procedure_docs)

    results = await retriever.aretrieve("振动摆度异常", top_k=5)

    assert isinstance(results, list)
    assert len(results) <= settings.reranker_top_k
    for item in results:
        assert "doc_id" in item
        assert "content" in item


@pytest.mark.asyncio
async def test_aretrieve_empty_store_returns_empty():
    """When both dense and sparse return nothing, aretrieve returns []."""
    retriever = _mock_retriever("procedure", [])

    results = await retriever.aretrieve("any query")

    assert results == []
