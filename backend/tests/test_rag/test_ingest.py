"""
Integration tests for the KB ingestion pipeline (REQ-004).

Uses a minimal two-document KB in a tmp_path fixture.  Real ingest wiring
(build_vectorstore / add_documents / BM25Index) is exercised end-to-end;
only the embedding function is replaced with a 16-dim stub so the test runs
without downloading BAAI/bge-large-zh-v1.5.

Covers:
  - test_ingest_creates_chroma_collection : first ingestion populates ChromaDB
                                            and the BM25 index is loadable through
                                            HybridRetriever
  - test_ingest_is_idempotent (xfail)     : documents REQ-004 AC "重复执行不产生
                                            重复文档" is not yet satisfied — current
                                            add_documents() appends on every run
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

_KB_DOC_TEMPLATE = """\
---
doc_id: {doc_id}
route_keys:
  - vibration_swing
---
# {title}

本文档是用于测试的伪知识库条目，编号 {doc_id}。
"""


class _FakeEmbeddings:
    """Deterministic 16-dim embeddings — no model download required."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(abs(hash(t)) % 100) / 100.0] * 16 for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return [float(abs(hash(text)) % 100) / 100.0] * 16


@pytest.fixture
def tmp_kb(tmp_path: Path) -> Path:
    """Minimal KB: 2 L2.TOPIC.* Markdown files under docs_internal/."""
    kb_dir = tmp_path / "docs_internal"
    kb_dir.mkdir()
    for i in range(2):
        doc_id = f"L2.TOPIC.TEST{i:03d}"
        (kb_dir / f"{doc_id}.md").write_text(
            _KB_DOC_TEMPLATE.format(doc_id=doc_id, title=f"测试文档 {i}"),
            encoding="utf-8",
        )
    return tmp_path


def _prepare_corpus_chunks(tmp_path: Path):
    """Load and chunk the KB docs; return only procedure-corpus chunks."""
    from app.rag.chunker import chunk_documents
    from app.rag.document_loader import load_kb_documents

    docs = list(load_kb_documents(tmp_path / "docs_internal"))
    chunks = chunk_documents(docs)
    return [
        c for c in chunks
        if (c.metadata.get("doc_id") or "").startswith("L2.TOPIC.")
    ]


def _ingest(corpus_chunks, chroma_dir: Path) -> Path:
    """
    Run the ingest pipeline through the real build_vectorstore / add_documents
    wiring, with embeddings replaced by _FakeEmbeddings.

    Returns the path to the saved BM25 pickle.
    """
    from app.config import settings
    from app.rag.bm25_index import BM25Index
    from app.rag.vectorstore import add_documents, build_vectorstore

    bm25_path = chroma_dir / "bm25_procedure.pkl"

    with (
        patch("app.rag.vectorstore._build_embeddings", return_value=_FakeEmbeddings()),
        patch.object(settings, "chroma_persist_dir", str(chroma_dir)),
        patch.object(settings, "vector_store_type", "chroma"),
    ):
        vs = build_vectorstore(collection="hydro_kb_procedure")
        add_documents(vs, corpus_chunks)
        count = vs._collection.count()

    bm25 = BM25Index(corpus_chunks)
    bm25.save(bm25_path)

    return bm25_path, count


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_ingest_creates_chroma_collection(tmp_kb: Path) -> None:
    """
    After one ingest run:
      1. ChromaDB collection is non-empty (real build_vectorstore wiring).
      2. BM25 pickle can be loaded and contains documents.
      3. A HybridRetriever backed by the loaded BM25 returns results.
    """
    from app.config import settings
    from app.rag.bm25_index import BM25Index
    from app.rag.hybrid_retriever import HybridRetriever
    from app.rag.vectorstore import build_vectorstore

    chroma_dir = tmp_kb / "chroma"
    chroma_dir.mkdir()
    corpus_chunks = _prepare_corpus_chunks(tmp_kb)
    bm25_path, _ = _ingest(corpus_chunks, chroma_dir)

    # 1. ChromaDB has documents
    with (
        patch("app.rag.vectorstore._build_embeddings", return_value=_FakeEmbeddings()),
        patch.object(settings, "chroma_persist_dir", str(chroma_dir)),
        patch.object(settings, "vector_store_type", "chroma"),
    ):
        vs = build_vectorstore(collection="hydro_kb_procedure")
        assert vs._collection.count() > 0, "ChromaDB collection is empty after ingest"

    # 2. BM25 pickle round-trip
    bm25 = BM25Index.load(bm25_path)
    assert len(bm25._docs) > 0, "Loaded BM25 index has no documents"

    # 3. HybridRetriever can query the persisted ChromaDB + loaded BM25 together
    #    (no mock_vs — uses the real Chroma collection written by _ingest)
    with (
        patch("app.rag.vectorstore._build_embeddings", return_value=_FakeEmbeddings()),
        patch.object(settings, "chroma_persist_dir", str(chroma_dir)),
        patch.object(settings, "vector_store_type", "chroma"),
    ):
        vs_real = build_vectorstore(collection="hydro_kb_procedure")
        retriever = HybridRetriever(vs_real, bm25, "procedure")
        results = asyncio.run(retriever.aretrieve("振动摆度异常"))
    assert len(results) > 0, "Persisted ChromaDB + BM25 must be queryable via HybridRetriever"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "REQ-004 AC '重复执行不产生重复文档' is not met: add_documents() appends on "
        "every call, doubling the collection count on re-run. "
        "Fix: add upsert-by-doc_id or pre-reset logic to the ingest pipeline, "
        "then remove this xfail marker. "
        "See tasks/archive/done/REQ-004.md TODO."
    ),
)
def test_ingest_is_idempotent(tmp_kb: Path) -> None:
    """
    Running the ingest pipeline twice with the same documents must NOT
    produce duplicate entries (strict idempotency per REQ-004 AC).

    Currently xfail: the implementation appends on every run.
    """
    chroma_dir = tmp_kb / "chroma"
    chroma_dir.mkdir()
    corpus_chunks = _prepare_corpus_chunks(tmp_kb)

    _, count_first = _ingest(corpus_chunks, chroma_dir)
    _, count_second = _ingest(corpus_chunks, chroma_dir)

    assert count_second == count_first, (
        f"Re-ingest duplicated documents: {count_first} → {count_second}. "
        "Ingest pipeline must use upsert or pre-reset to satisfy REQ-004."
    )
