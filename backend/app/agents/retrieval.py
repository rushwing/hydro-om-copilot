"""
retrieval node — runs hybrid (BM25 + dense) retrieval for three sub-corpora
in parallel and merges results into RetrievedContext.
"""

import asyncio

from app.agents.state import AgentState, RetrievedContext
from app.rag.hybrid_retriever import HybridRetriever

# Lazy-loaded singleton retrievers (initialised at startup via lifespan)
_retrievers: dict[str, HybridRetriever] = {}


def get_retriever(corpus: str) -> HybridRetriever:
    if corpus not in _retrievers:
        from app.rag.hybrid_retriever import build_retriever
        _retrievers[corpus] = build_retriever(corpus)
    return _retrievers[corpus]


async def _retrieve(corpus: str, query: str, topic: str | None) -> list[dict]:
    retriever = get_retriever(corpus)
    return await retriever.aretrieve(query, topic_filter=topic)


async def retrieval_node(state: AgentState) -> dict:
    query = state["raw_query"]
    if state.get("ocr_text"):
        query = f"{query}\n\n[截图内容]\n{state['ocr_text']}"

    topic = state.get("topic")

    procedure_task = asyncio.create_task(_retrieve("procedure", query, topic))
    rule_task = asyncio.create_task(_retrieve("rule", query, topic))
    case_task = asyncio.create_task(_retrieve("case", query, topic))

    procedure_docs, rule_docs, case_docs = await asyncio.gather(
        procedure_task, rule_task, case_task
    )

    sources = list(
        {doc["doc_id"] for doc in procedure_docs + rule_docs + case_docs if "doc_id" in doc}
    )

    return {
        "retrieved": RetrievedContext(
            procedure_docs=procedure_docs,
            rule_docs=rule_docs,
            case_docs=case_docs,
        ),
        "sources": sources,
    }
