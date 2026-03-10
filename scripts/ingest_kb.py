#!/usr/bin/env python3
"""
Knowledge Base Ingestion Script
================================
Loads all Markdown documents from knowledge_base/docs_internal,
chunks them, embeds, and stores in ChromaDB + BM25 pickle files.

Usage:
    cd hydro-om-copilot
    uv run scripts/ingest_kb.py [--kb-dir <path>] [--reset]
"""

import argparse
import sys
from pathlib import Path

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.config import settings
from app.rag.document_loader import load_kb_documents
from app.rag.chunker import chunk_documents
from app.rag.vectorstore import build_vectorstore, add_documents
from app.rag.bm25_index import BM25Index

# Corpus → doc_id prefixes mapping
CORPUS_MAP = {
    "procedure": ["L2.TOPIC.", "L1."],
    "rule": ["L2.SUPPORT.RULE"],
    "case": ["L2.SUPPORT.CASE"],
}


def _filter_chunks(chunks, prefixes):
    return [c for c in chunks if any(
        (c.metadata.get("doc_id") or "").startswith(p) for p in prefixes
    )]


def main():
    parser = argparse.ArgumentParser(description="Ingest knowledge base into vector store")
    parser.add_argument("--kb-dir", default=settings.kb_docs_dir)
    parser.add_argument("--reset", action="store_true", help="Clear existing collections first")
    args = parser.parse_args()

    kb_dir = Path(args.kb_dir)
    if not kb_dir.exists():
        print(f"[ERROR] KB directory not found: {kb_dir}")
        sys.exit(1)

    print(f"[1/4] Loading documents from {kb_dir} …")
    docs = list(load_kb_documents(kb_dir))
    print(f"      Loaded {len(docs)} documents")

    print("[2/4] Chunking …")
    chunks = chunk_documents(docs)
    print(f"      {len(chunks)} chunks produced")

    vector_store_dir = Path(settings.chroma_persist_dir)
    vector_store_dir.mkdir(parents=True, exist_ok=True)

    for corpus, prefixes in CORPUS_MAP.items():
        corpus_chunks = _filter_chunks(chunks, prefixes)
        print(f"[3/4] Ingesting corpus '{corpus}': {len(corpus_chunks)} chunks …")

        # Dense vector store
        vs = build_vectorstore(collection=f"hydro_kb_{corpus}")
        if args.reset:
            try:
                vs.delete_collection()
                vs = build_vectorstore(collection=f"hydro_kb_{corpus}")
            except Exception:
                pass
        add_documents(vs, corpus_chunks)

        # BM25 index
        bm25 = BM25Index(corpus_chunks)
        bm25_path = vector_store_dir / f"bm25_{corpus}.pkl"
        bm25.save(bm25_path)
        print(f"      BM25 index saved → {bm25_path}")

    print("[4/4] Done. Knowledge base is ready for retrieval.")


if __name__ == "__main__":
    main()
