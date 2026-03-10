"""
Vector store abstraction supporting ChromaDB (dev) and Qdrant (prod).
"""

from __future__ import annotations

from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore

from app.config import settings


def _build_embeddings():
    from langchain_community.embeddings import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(
        model_name=settings.embedding_model,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def build_vectorstore(collection: str = "hydro_kb") -> VectorStore:
    embeddings = _build_embeddings()

    if settings.vector_store_type == "qdrant":
        from langchain_qdrant import QdrantVectorStore
        from qdrant_client import QdrantClient
        from qdrant_client.http.models import Distance, VectorParams

        client = QdrantClient(url=settings.qdrant_url)
        if collection not in [c.name for c in client.get_collections().collections]:
            client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
            )
        return QdrantVectorStore(client=client, collection_name=collection, embedding=embeddings)

    # Default: ChromaDB
    from langchain_chroma import Chroma

    return Chroma(
        collection_name=collection,
        embedding_function=embeddings,
        persist_directory=settings.chroma_persist_dir,
    )


def add_documents(vectorstore: VectorStore, chunks: list[Document]) -> None:
    vectorstore.add_documents(chunks)
