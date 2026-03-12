"""
Splits KB documents into smaller chunks suitable for embedding.

Strategy:
  1. MarkdownHeaderTextSplitter — split by heading, carrying h1/h2/h3 as metadata.
  2. Table-aware split — detect Markdown tables, keep each row intact, and prepend
     the header row to every table chunk so the LLM always knows column names.
  3. RecursiveCharacterTextSplitter — further split oversized prose chunks.

L3 stub documents (sparse template content) use a smaller chunk size (300 chars)
to avoid near-empty chunks that waste embedding space.
"""

from __future__ import annotations

import re

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from app.config import settings

_HEADERS = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
    ("####", "h4"),
]

_SEPARATORS = ["\n\n", "\n", "。", "；", " ", ""]

# Match a complete Markdown table: header row + separator row + ≥1 data row
_TABLE_RE = re.compile(
    r"(\|[^\n]+\|\n\|[-| :]+\|\n(?:\|[^\n]+\|\n?)+)",
    re.MULTILINE,
)


def _make_splitters() -> tuple[RecursiveCharacterTextSplitter, RecursiveCharacterTextSplitter]:
    prose = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=_SEPARATORS,
    )
    l3 = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size_l3,
        chunk_overlap=settings.chunk_overlap_l3,
        separators=_SEPARATORS,
    )
    return prose, l3


def _split_table(table_text: str) -> list[str]:
    """
    Split a Markdown table into chunks of at most settings.table_rows_per_chunk rows.
    Each chunk starts with the original header + separator rows so that column
    context is never lost.
    """
    lines = table_text.strip().split("\n")
    if len(lines) < 3:
        return [table_text]

    header = lines[0]     # | Col1 | Col2 | …
    separator = lines[1]  # |------|------|
    data_rows = lines[2:]

    result: list[str] = []
    for i in range(0, len(data_rows), settings.table_rows_per_chunk):
        batch = data_rows[i : i + settings.table_rows_per_chunk]
        result.append("\n".join([header, separator, *batch]))

    return result or [table_text]


def _split_text_with_tables(
    text: str, splitter: RecursiveCharacterTextSplitter
) -> list[str]:
    """
    Split text while keeping Markdown tables intact.

    Non-table prose segments are handled by `splitter`.
    Table segments are split row-wise via `_split_table`, with the header row
    prepended to each chunk.
    """
    result: list[str] = []
    last_end = 0

    for match in _TABLE_RE.finditer(text):
        # Prose before this table
        pre = text[last_end : match.start()].strip()
        if pre:
            result.extend(splitter.split_text(pre))

        result.extend(_split_table(match.group()))
        last_end = match.end()

    # Remaining prose after the last table (or the whole text if no tables)
    post = text[last_end:].strip()
    if post:
        result.extend(splitter.split_text(post))

    return result


def _is_l3(doc: Document) -> bool:
    source = doc.metadata.get("source", "")
    doc_id = doc.metadata.get("doc_id", "")
    return "L3_" in source or str(doc_id).startswith("L3.")


def chunk_documents(docs: list[Document]) -> list[Document]:
    """Split documents into chunks, preserving parent metadata."""
    chunks: list[Document] = []
    prose_splitter, l3_splitter = _make_splitters()
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=_HEADERS,
        strip_headers=False,
    )

    for doc in docs:
        splitter = l3_splitter if _is_l3(doc) else prose_splitter

        try:
            header_chunks = header_splitter.split_text(doc.page_content)
        except Exception:
            header_chunks = [Document(page_content=doc.page_content)]

        for hc in header_chunks:
            text_pieces = _split_text_with_tables(hc.page_content, splitter)
            for text in text_pieces:
                merged_meta = {**doc.metadata, **hc.metadata}
                chunks.append(Document(page_content=text, metadata=merged_meta))

    return chunks
