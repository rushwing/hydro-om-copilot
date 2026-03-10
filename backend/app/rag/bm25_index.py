"""
BM25 sparse retriever backed by jieba Chinese tokenisation.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import jieba
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi


def _tokenize(text: str) -> list[str]:
    return list(jieba.cut(text))


class BM25Index:
    def __init__(self, docs: list[Document]) -> None:
        self._docs = docs
        tokenized = [_tokenize(d.page_content) for d in docs]
        self._bm25 = BM25Okapi(tokenized)

    def retrieve(self, query: str, top_k: int = 10) -> list[Document]:
        tokens = _tokenize(query)
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return [self._docs[i] for i, _ in ranked[:top_k]]

    def save(self, path: str | Path) -> None:
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, path: str | Path) -> BM25Index:
        with open(path, "rb") as f:
            return pickle.load(f)
