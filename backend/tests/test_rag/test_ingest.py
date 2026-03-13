"""
Integration tests for the KB ingestion pipeline (REQ-004).

Uses a minimal two-document KB in a tmp_path fixture with fake embeddings
so the test runs without downloading the real BAAI/bge-large-zh-v1.5 model.

Covers:
  - test_ingest_creates_chroma_collection : first ingestion creates a non-empty collection
  - test_ingest_is_idempotent             : running twice doesn't crash and keeps docs
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pytest
from langchain_core.documents import Document


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

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [[float(abs(hash(t)) % 100) / 100.0] * 16 for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return [float(abs(hash(text)) % 100) / 100.0] * 16


@pytest.fixture
def tmp_kb(tmp_path: Path) -> Path:
    """Create a minimal KB with 2 Markdown files under docs_internal/."""
    kb_dir = tmp_path / "docs_internal"
    kb_dir.mkdir()
    for i in range(2):
        doc_id = f"L2.TOPIC.TEST{i:03d}"
        (kb_dir / f"{doc_id}.md").write_text(
            _KB_DOC_TEMPLATE.format(doc_id=doc_id, title=f"测试文档 {i}"),
            encoding="utf-8",
        )
    return tmp_path


def _run_ingest(tmp_path: Path) -> tuple:
    """
    Execute the core ingest pipeline steps against tmp_path.

    Returns (vectorstore, bm25, chunk_count).
    """
    from langchain_chroma import Chroma

    from app.rag.bm25_index import BM25Index
    from app.rag.chunker import chunk_documents
    from app.rag.document_loader import load_kb_documents

    kb_dir = tmp_path / "docs_internal"
    chroma_dir = tmp_path / "chroma"
    chroma_dir.mkdir(exist_ok=True)

    docs = list(load_kb_documents(kb_dir))
    chunks = chunk_documents(docs)

    # Only the "procedure" corpus (L2.TOPIC.*) for simplicity
    corpus_chunks = [
        c for c in chunks
        if (c.metadata.get("doc_id") or "").startswith("L2.TOPIC.")
    ]

    vs = Chroma(
        collection_name="hydro_kb_ingest_test",
        embedding_function=_FakeEmbeddings(),
        persist_directory=str(chroma_dir),
    )
    vs.add_documents(corpus_chunks)

    bm25 = BM25Index(corpus_chunks)
    bm25.save(chroma_dir / "bm25_test.pkl")

    return vs, bm25, len(corpus_chunks)


def test_ingest_creates_chroma_collection(tmp_kb: Path) -> None:
    """First ingestion populates the ChromaDB collection with at least one chunk."""
    vs, bm25, chunk_count = _run_ingest(tmp_kb)

    assert chunk_count > 0, "Expected at least one corpus chunk"
    count = vs._collection.count()
    assert count > 0, f"ChromaDB collection is empty after ingest (chunk_count={chunk_count})"


def test_ingest_is_idempotent(tmp_kb: Path) -> None:
    """Running the ingest pipeline twice does not crash and preserves existing docs."""
    vs_first, _, count_first = _run_ingest(tmp_kb)
    initial_count = vs_first._collection.count()
    assert initial_count > 0

    # Second run (no --reset flag → append semantics)
    vs_second, _, _ = _run_ingest(tmp_kb)
    second_count = vs_second._collection.count()

    # Without explicit reset, count should be >= initial (no data loss).
    assert second_count >= initial_count, (
        f"Second run shrunk the collection: {second_count} < {initial_count}"
    )
