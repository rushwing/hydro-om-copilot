"""
Hybrid retriever: BM25 + dense vector search fused via Reciprocal Rank Fusion (RRF).

Retrieval design:
- P1a: Corpus filter uses doc_id prefix matching so L0/L1/L3 docs are included.
- P1b: After primary retrieval, supplementary retrievers from related corpora
       (rule + case for procedure queries) are queried and merged.
- P2:  topic_filter applies post-retrieval filtering on route_keys metadata.
- P3:  TODO — inject L1.ROUTER.001 chunks as mandatory system context at the
       graph/agent level (outside the retriever boundary).
"""

from __future__ import annotations

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore

from app.config import settings
from app.rag.bm25_index import BM25Index

# P1a: prefix-based corpus filter — allows L0 methodology and L3 site docs through
_CORPUS_PREFIX_MAP: dict[str, list[str]] = {
    "procedure": ["L2.TOPIC.", "L1.", "L0."],
    "rule":      ["L2.SUPPORT.RULE.", "L0."],
    "case":      ["L2.SUPPORT.CASE.", "L0."],
}

# P1b: supplementary corpora to query after primary retrieval
_SUPPLEMENTARY_CORPORA: dict[str, list[str]] = {
    "procedure": ["rule", "case"],
    "rule":      [],
    "case":      [],
}


def _rrf(lists: list[list[Document]], k: int = 60) -> list[Document]:
    """Reciprocal Rank Fusion over multiple ranked lists."""
    scores: dict[str, float] = {}
    doc_map: dict[str, Document] = {}

    for ranked in lists:
        for rank, doc in enumerate(ranked):
            # Use doc_id + first 80 chars to avoid false deduplication of table header chunks
            key = doc.metadata.get("doc_id", "") + "|" + doc.page_content[:80]
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            doc_map[key] = doc

    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [doc_map[key] for key, _ in ordered]


def _matches_topic(doc: Document, topic_filter: str) -> bool:
    """P2: Check if a chunk's route_keys includes the requested topic."""
    route_keys = doc.metadata.get("route_keys", [])
    if isinstance(route_keys, list):
        return topic_filter in route_keys
    if isinstance(route_keys, str):
        # Chroma may serialize lists as comma-separated strings
        return topic_filter in [k.strip() for k in route_keys.split(",")]
    return False


def _apply_corpus_filter(docs: list[Document], corpus: str) -> list[Document]:
    """P1a: Keep only docs whose doc_id starts with an allowed prefix."""
    prefixes = _CORPUS_PREFIX_MAP.get(corpus, [])
    if not prefixes:
        return docs
    return [
        d for d in docs
        if any(d.metadata.get("doc_id", "").startswith(p) for p in prefixes)
    ]


class HybridRetriever:
    def __init__(
        self,
        vectorstore: VectorStore,
        bm25: BM25Index,
        corpus: str,
        supplementary: list[HybridRetriever] | None = None,
    ) -> None:
        self._vs = vectorstore
        self._bm25 = bm25
        self._corpus = corpus
        self._supplementary: list[HybridRetriever] = supplementary or []

    async def aretrieve(
        self,
        query: str,
        top_k: int = 10,
        topic_filter: str | None = None,
    ) -> list[dict]:
        # Dense + sparse retrieval
        dense_docs = await self._vs.asimilarity_search(query, k=top_k)
        sparse_docs = self._bm25.retrieve(query, top_k=top_k)

        # P2: topic_filter — apply before fusion to bias toward relevant route_keys
        if topic_filter:
            dense_filtered = [d for d in dense_docs if _matches_topic(d, topic_filter)]
            sparse_filtered = [d for d in sparse_docs if _matches_topic(d, topic_filter)]
            # Fall back to unfiltered if filtering yields too few results
            if len(dense_filtered) + len(sparse_filtered) >= 3:
                dense_docs, sparse_docs = dense_filtered, sparse_filtered

        # RRF fusion of primary results
        fused = _rrf([dense_docs, sparse_docs])

        # P1a: corpus prefix filter
        fused = _apply_corpus_filter(fused, self._corpus)

        # P1b: supplementary retrieval from related corpora (e.g., rule+case for procedure).
        # Only inject if the chunk also passes topic_filter to avoid mixing unrelated topics.
        if self._supplementary:
            supp_lists: list[list[Document]] = []
            for supp in self._supplementary:
                supp_dense = await supp._vs.asimilarity_search(query, k=3)
                supp_sparse = supp._bm25.retrieve(query, top_k=3)
                supp_fused = _rrf([supp_dense, supp_sparse])
                supp_fused = _apply_corpus_filter(supp_fused, supp._corpus)
                # Apply the same topic_filter so cross-corpus injection stays on-topic
                if topic_filter:
                    supp_fused = [d for d in supp_fused if _matches_topic(d, topic_filter)]
                supp_lists.append(supp_fused[:2])  # Take top-2 from each supplementary corpus

            supplementary_docs = [doc for lst in supp_lists for doc in lst]
            # Append after primary results (lower priority); skip duplicates
            primary_keys = {d.metadata.get("doc_id", "") + "|" + d.page_content[:80] for d in fused}
            fused = fused + [
                d for d in supplementary_docs
                if d.metadata.get("doc_id", "") + "|" + d.page_content[:80] not in primary_keys
            ]

        # Rerank the combined candidate set
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


def build_retriever(corpus: str, with_supplementary: bool = True) -> HybridRetriever:
    """
    Build a HybridRetriever for a given corpus label.

    When with_supplementary=True (default), the "procedure" corpus retriever
    also holds supplementary retrievers for "rule" and "case" corpora (P1b).
    """
    from app.rag.vectorstore import build_vectorstore

    vs = build_vectorstore(collection=f"hydro_kb_{corpus}")
    bm25_path = f"./knowledge_base/vector_store/bm25_{corpus}.pkl"
    try:
        bm25 = BM25Index.load(bm25_path)
    except FileNotFoundError:
        bm25 = BM25Index([])

    supplementary: list[HybridRetriever] = []
    if with_supplementary:
        for supp_corpus in _SUPPLEMENTARY_CORPORA.get(corpus, []):
            supplementary.append(build_retriever(supp_corpus, with_supplementary=False))

    return HybridRetriever(vs, bm25, corpus, supplementary=supplementary)
