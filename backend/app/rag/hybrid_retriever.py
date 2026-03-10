"""
Hybrid retriever: BM25 + dense vector search fused via Reciprocal Rank Fusion (RRF).
"""

from __future__ import annotations

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore

from app.config import settings
from app.rag.bm25_index import BM25Index

_CORPUS_FILTER_MAP = {
    "procedure": ["L2.TOPIC.VIB.001", "L2.TOPIC.GOV.001", "L2.TOPIC.BEAR.001",
                  "L1.ROUTER.001", "L1.OVERVIEW.001"],
    "rule": ["L2.SUPPORT.RULE.001"],
    "case": ["L2.SUPPORT.CASE.001"],
}


def _rrf(
    lists: list[list[Document]],
    k: int = 60,
) -> list[Document]:
    """Reciprocal Rank Fusion over multiple ranked lists."""
    scores: dict[str, float] = {}
    doc_map: dict[str, Document] = {}

    for ranked in lists:
        for rank, doc in enumerate(ranked):
            key = doc.metadata.get("doc_id", "") + "|" + doc.page_content[:60]
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            doc_map[key] = doc

    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [doc_map[key] for key, _ in ordered]


class HybridRetriever:
    def __init__(self, vectorstore: VectorStore, bm25: BM25Index, corpus: str) -> None:
        self._vs = vectorstore
        self._bm25 = bm25
        self._corpus = corpus

    async def aretrieve(
        self,
        query: str,
        top_k: int = 10,
        topic_filter: str | None = None,
    ) -> list[dict]:
        # Dense retrieval
        dense_docs = await self._vs.asimilarity_search(query, k=top_k)

        # Sparse retrieval
        sparse_docs = self._bm25.retrieve(query, top_k=top_k)

        # RRF fusion
        fused = _rrf([dense_docs, sparse_docs])

        # Filter to corpus doc_ids
        allowed_ids = _CORPUS_FILTER_MAP.get(self._corpus, [])
        if allowed_ids:
            fused = [d for d in fused if d.metadata.get("doc_id") in allowed_ids]

        # Rerank if available
        fused = _rerank(query, fused[: settings.reranker_top_k * 2])

        return [
            {"doc_id": d.metadata.get("doc_id"), "content": d.page_content, **d.metadata}
            for d in fused[: settings.reranker_top_k]
        ]


def _rerank(query: str, docs: list[Document]) -> list[Document]:
    """Best-effort reranking via BGE-reranker; degrades gracefully."""
    try:
        from FlagEmbedding import FlagReranker

        reranker = FlagReranker(settings.reranker_model, use_fp16=True)
        pairs = [[query, d.page_content] for d in docs]
        scores = reranker.compute_score(pairs)
        ranked = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
        return [d for _, d in ranked]
    except Exception:
        return docs


def build_retriever(corpus: str) -> HybridRetriever:
    """Build a HybridRetriever for a given corpus label."""
    from app.rag.vectorstore import build_vectorstore

    vs = build_vectorstore(collection=f"hydro_kb_{corpus}")
    # BM25 index is expected to exist after ingest_kb.py runs
    bm25_path = f"./knowledge_base/vector_store/bm25_{corpus}.pkl"
    try:
        bm25 = BM25Index.load(bm25_path)
    except FileNotFoundError:
        # Empty index — retrieval will rely on dense only until ingest is run
        bm25 = BM25Index([])
    return HybridRetriever(vs, bm25, corpus)
