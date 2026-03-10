#!/usr/bin/env python3
"""
Validates YAML front-matter metadata completeness across all KB documents.

Usage:
    uv run scripts/validate_kb.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.rag.document_loader import load_kb_documents
from app.config import settings

REQUIRED_FIELDS = ["doc_id", "doc_level", "route_keys"]
OPTIONAL_FIELDS = ["upstream", "downstream", "title"]


def main():
    docs = list(load_kb_documents(settings.kb_docs_dir))
    errors = []
    warnings = []

    for doc in docs:
        m = doc.metadata
        source = m.get("source", "?")
        for field in REQUIRED_FIELDS:
            if not m.get(field):
                errors.append(f"MISSING {field}: {source}")
        for field in OPTIONAL_FIELDS:
            if not m.get(field):
                warnings.append(f"WARN missing {field}: {source}")

    if warnings:
        print("\n".join(warnings))
    if errors:
        print("\n".join(errors))
        sys.exit(1)

    print(f"✓ All {len(docs)} documents passed validation.")


if __name__ == "__main__":
    main()
