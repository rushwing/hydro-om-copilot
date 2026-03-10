"""
Splits KB documents into smaller chunks suitable for embedding.
Strategy: heading-aware splitting that respects Markdown structure.
"""

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

_HEADERS = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
    ("####", "h4"),
]

_FALLBACK_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=600,
    chunk_overlap=80,
    separators=["\n\n", "\n", "。", "；", " ", ""],
)


def chunk_documents(docs: list[Document]) -> list[Document]:
    """Split documents into chunks, preserving parent metadata."""
    chunks: list[Document] = []
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=_HEADERS,
        strip_headers=False,
    )

    for doc in docs:
        try:
            header_chunks = header_splitter.split_text(doc.page_content)
        except Exception:
            header_chunks = [Document(page_content=doc.page_content)]

        for hc in header_chunks:
            # Further split if the heading chunk is still too large
            sub_chunks = _FALLBACK_SPLITTER.split_documents([hc])
            for sc in sub_chunks:
                # Merge parent metadata, chunk metadata takes priority
                merged_meta = {**doc.metadata, **sc.metadata}
                chunks.append(Document(page_content=sc.page_content, metadata=merged_meta))

    return chunks
