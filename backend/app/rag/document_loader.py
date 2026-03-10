"""
Loads Markdown knowledge-base documents, parses YAML front-matter,
and returns LangChain Document objects enriched with metadata.
"""

import re
from collections.abc import Iterator
from pathlib import Path

import frontmatter
from langchain_core.documents import Document

_YAML_FENCE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def load_kb_documents(kb_dir: str | Path) -> Iterator[Document]:
    """
    Walk ``kb_dir`` recursively, load every .md file, parse YAML front-matter,
    and yield a LangChain Document per file.
    """
    kb_path = Path(kb_dir)
    for md_file in sorted(kb_path.rglob("*.md")):
        try:
            post = frontmatter.load(md_file)
        except Exception:
            # Fallback: treat entire file as plain text with no metadata
            content = md_file.read_text(encoding="utf-8")
            yield Document(
                page_content=content,
                metadata={"source": str(md_file), "doc_id": md_file.stem},
            )
            continue

        metadata = dict(post.metadata)
        metadata.setdefault("doc_id", md_file.stem)
        metadata.setdefault("source", str(md_file))

        # Normalise upstream/downstream to lists
        for key in ("upstream", "downstream", "route_keys"):
            val = metadata.get(key)
            if isinstance(val, str):
                metadata[key] = [v.strip() for v in val.split(",")]

        yield Document(page_content=post.content, metadata=metadata)
