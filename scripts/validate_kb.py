#!/usr/bin/env python3
"""
Validates KB documents against harness/kb-ingestion-standard.md auto-checkable rules.

Implemented checks (all 7 from harness § 3 "自动可检查"):
  1. Required frontmatter fields (doc_id, doc_level, knowledge_type, route_keys)
  2. doc_id format: L[0-3].[A-Z]+(\.[A-Z]+)*.\d{3}
  3. No empty headings (heading immediately followed by another heading)
  4. Table column names don't contain pure generic words (字段 / 示例 / 值)
  5. Table column names don't contain / joining two CJK concepts
  6. L3 docs (path contains L3_ or doc_level=L3) have upstream_docs field
  7. WARN: threshold column names (containing 阈值/告警/跳闸) should include a unit (℃/MPa/mm/μm)

Usage (from project root):
    uv run --project backend scripts/validate_kb.py

Or directly:
    python scripts/validate_kb.py
"""

import re
import sys
from pathlib import Path

try:
    import yaml  # PyYAML — transitive dep of langchain
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_KB_DIR = Path(__file__).parent.parent / "knowledge_base" / "docs_internal"

REQUIRED_FIELDS = ["doc_id", "doc_level", "knowledge_type", "route_keys"]
L3_REQUIRED_FIELDS = ["upstream_docs"]

# Harness § 2.1 — doc_id format regex
_DOC_ID_RE = re.compile(r"^L[0-3]\.[A-Z]+(\.[A-Z]+)*\.\d{3}$")

# Harness § 2.3 — forbidden generic column names (standalone)
_GENERIC_COLUMNS: set[str] = {"字段", "示例", "值"}

# Harness § 2.5 — units expected in threshold-related column names
# Only pure threshold columns (short names) are checked; long descriptive columns like
# "规则内容与阈值" are excluded because units appear inside cell text, not in the header.
_THRESHOLD_COLUMN_KEYWORDS = {"报警阈值", "跳闸阈值"}
_UNITS: set[str] = {"℃", "MPa", "kPa", "mm", "μm", "r/min", "Hz", "kV", "MW"}

# Table header/separator patterns
_TABLE_HEADER_RE = re.compile(r"^\|(.+)\|$")
_TABLE_SEP_RE = re.compile(r"^\|[-| :]+\|$")

# ---------------------------------------------------------------------------
# Frontmatter parser
# ---------------------------------------------------------------------------


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (metadata_dict, body_text). Supports PyYAML when available."""
    if not text.startswith("---"):
        return {}, text

    end = text.find("\n---", 3)
    if end == -1:
        return {}, text

    yaml_text = text[3:end].strip()
    body = text[end + 4 :].lstrip("\n")

    if _YAML_AVAILABLE:
        try:
            metadata = yaml.safe_load(yaml_text) or {}
        except yaml.YAMLError:
            metadata = {}
    else:
        metadata = _simple_yaml_parse(yaml_text)

    return metadata, body


def _simple_yaml_parse(yaml_text: str) -> dict:
    """Minimal YAML parser — only handles the subset used in KB frontmatter."""
    metadata: dict = {}
    current_key: str | None = None
    current_list: list | None = None

    for line in yaml_text.split("\n"):
        if not line.strip():
            continue
        if line.startswith("  - "):
            if current_list is not None:
                current_list.append(line[4:].strip())
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            current_list = None
            if not value:
                current_key = key
                current_list = []
                metadata[key] = current_list
            elif value.startswith("["):
                items = value.strip("[]").split(",")
                metadata[key] = [i.strip() for i in items if i.strip()]
                current_key = key
            else:
                metadata[key] = value
                current_key = key

    return metadata


# ---------------------------------------------------------------------------
# Content checks
# ---------------------------------------------------------------------------


def _extract_table_headers(body: str) -> list[tuple[int, list[str]]]:
    """Return list of (1-indexed line_num, [col_names]) for each table header."""
    lines = body.split("\n")
    results = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not _TABLE_HEADER_RE.match(stripped):
            continue
        if i + 1 < len(lines) and _TABLE_SEP_RE.match(lines[i + 1].strip()):
            cols = [c.strip() for c in stripped.split("|")[1:-1]]
            results.append((i + 1, cols))
    return results


def _has_cjk(s: str) -> bool:
    return any("\u4e00" <= c <= "\u9fff" for c in s)


def _has_unit(s: str) -> bool:
    return any(u in s for u in _UNITS)


def check_doc_id(doc_id: str, source: str) -> list[str]:
    if not _DOC_ID_RE.match(str(doc_id)):
        return [
            f"[ERROR] INVALID_DOC_ID '{doc_id}' — does not match "
            f"L[0-3].[A-Z]+(.[A-Z]+)*.\\d{{3}}: {source}"
        ]
    return []


def check_empty_headings(body: str, source: str) -> list[str]:
    """
    Detect ## (H2) section headings immediately followed by another ## heading with no
    content between them — these produce empty chunks after splitting.

    Intentionally NOT flagged (valid Markdown structure):
      - # Title → ## Section   (document title leading into first section)
      - ## Section → ### Sub   (section expanding into subsections)
    """
    errors = []
    lines = body.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Only check ## level (the RAG chunking boundary)
        if not stripped.startswith("## "):
            continue
        # Scan ahead for next non-blank line
        for j in range(i + 1, min(i + 8, len(lines))):
            next_line = lines[j].strip()
            if not next_line:
                continue
            # Flag only if the very next content is ALSO a ## heading (same level)
            if next_line.startswith("## "):
                errors.append(
                    f"[ERROR] EMPTY_HEADING line {i + 1}: "
                    f"'{stripped[:60]}' has no content before next ## heading: {source}"
                )
            break  # stop after first non-blank line
    return errors


def check_table_columns(body: str, source: str) -> tuple[list[str], list[str]]:
    """
    Returns (errors, warnings).
    Errors: generic column names, compound column names with /.
    Warnings: threshold column names missing units.
    """
    errors: list[str] = []
    warnings: list[str] = []

    for line_num, cols in _extract_table_headers(body):
        for col in cols:
            col_stripped = col.strip()
            if not col_stripped:
                continue

            # Check 4: generic column names (exact match, stripped of unit parens)
            col_bare = re.sub(r"[（(][^）)]*[）)]", "", col_stripped).strip()
            if col_bare in _GENERIC_COLUMNS:
                errors.append(
                    f"[ERROR] GENERIC_COLUMN line {line_num}: "
                    f"column '{col_stripped}' is a prohibited generic name: {source}"
                )

            # Check 5: compound column name with / between CJK concepts
            if "/" in col_stripped:
                parts = col_stripped.split("/", 1)
                left, right = parts[0].strip(), parts[1].strip()
                # Only flag when both sides contain CJK (concept/concept), not units (mm/s)
                if _has_cjk(left) and _has_cjk(right):
                    errors.append(
                        f"[ERROR] COMPOUND_COLUMN line {line_num}: "
                        f"column '{col_stripped}' joins two concepts with /: {source}"
                    )

            # Check 7 (warn): threshold-related columns should declare a unit
            is_threshold_col = any(kw in col_stripped for kw in _THRESHOLD_COLUMN_KEYWORDS)
            if is_threshold_col and not _has_unit(col_stripped):
                warnings.append(
                    f"[WARN]  MISSING_UNIT line {line_num}: "
                    f"threshold column '{col_stripped}' has no unit annotation: {source}"
                )

    return errors, warnings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    kb_dir = _KB_DIR
    if not kb_dir.exists():
        print(f"ERROR: KB directory not found: {kb_dir}", file=sys.stderr)
        sys.exit(1)

    md_files = sorted(kb_dir.rglob("*.md"))
    if not md_files:
        print(f"ERROR: No .md files found in {kb_dir}", file=sys.stderr)
        sys.exit(1)

    all_errors: list[str] = []
    all_warnings: list[str] = []

    for path in md_files:
        source = str(path.relative_to(kb_dir))
        text = path.read_text(encoding="utf-8")
        metadata, body = _parse_frontmatter(text)

        # --- Check 1: Required frontmatter fields ---
        for field in REQUIRED_FIELDS:
            val = metadata.get(field)
            if not val:
                all_errors.append(f"[ERROR] MISSING_FIELD '{field}': {source}")

        # --- Check 2: doc_id format ---
        doc_id = metadata.get("doc_id", "")
        if doc_id:
            all_errors.extend(check_doc_id(str(doc_id), source))

        # --- Check 6: L3 upstream_docs ---
        is_l3 = "L3_" in str(path) or str(metadata.get("doc_level", "")).upper() == "L3"
        if is_l3 and not metadata.get("upstream_docs"):
            all_errors.append(
                f"[ERROR] MISSING_FIELD 'upstream_docs' (required for L3): {source}"
            )

        # --- Checks 3, 4, 5, 7 on body content ---
        all_errors.extend(check_empty_headings(body, source))
        col_errors, col_warnings = check_table_columns(body, source)
        all_errors.extend(col_errors)
        all_warnings.extend(col_warnings)

        # Optional upstream_docs reminder for non-L0/L3 docs
        if (
            not is_l3
            and not metadata.get("upstream_docs")
            and str(metadata.get("doc_level", "")).upper() not in ("L0",)
        ):
            all_warnings.append(f"[WARN]  MISSING upstream_docs (recommended): {source}")

    # --- Report ---
    if all_warnings:
        print("\n".join(all_warnings))

    if all_errors:
        print("\n".join(all_errors))
        print(
            f"\n✗ {len(all_errors)} error(s) found across {len(md_files)} documents.",
            file=sys.stderr,
        )
        sys.exit(1)

    warn_count = len(all_warnings)
    warn_suffix = f"  ({warn_count} warning(s))" if warn_count else ""
    print(f"✓ All {len(md_files)} documents passed validation.{warn_suffix}")


if __name__ == "__main__":
    main()
