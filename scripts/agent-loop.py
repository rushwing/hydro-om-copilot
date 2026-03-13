#!/usr/bin/env python3
"""
agent-loop.py — Git-Native Agent Loop stub

Scans tasks/ for claimable work items and prints a summary.
Intended to be run by GitHub Actions after each PR merge to main.

Current status: stub — prints claimable tasks only.
Actual agent invocation (harness.sh tc-design / implement) is triggered
manually until the loop is proven stable.

Two-pass scan (see harness/harness-index.md §自动化流程):
  Pass 1 — TC design:     status=ready, owner=unassigned, test_case_ref empty,
                           depends_on all done
  Pass 2 — Implementation: status=test_designed, owner=unassigned,
                            depends_on all done
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FEATURES_DIR = REPO_ROOT / "tasks" / "features"
BUGS_DIR     = REPO_ROOT / "tasks" / "bugs"
ARCHIVE_DONE = REPO_ROOT / "tasks" / "archive" / "done"
ARCHIVE_CANCELLED = REPO_ROOT / "tasks" / "archive" / "cancelled"

# Terminal status per work-item type (see requirement-standard.md and bug-standard.md)
_REQ_DONE_STATUSES = {"done"}
_BUG_DONE_STATUSES = {"closed"}


def parse_frontmatter(path: Path) -> dict:
    """Extract key: value pairs from YAML frontmatter (--- delimited).

    Supports both inline values  (key: value)
    and YAML block lists          (key:\n  - item1\n  - item2).
    Block list values are stored as '[item1, item2]' so that the existing
    _parse_list_field() helper can consume them without changes.
    """
    fields: dict = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return fields
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return fields

    pending_key: str | None = None
    pending_items: list[str] = []

    def _flush() -> None:
        if pending_key is not None:
            fields[pending_key] = "[" + ", ".join(pending_items) + "]"

    for line in lines[1:]:
        if line.strip() == "---":
            _flush()
            break
        # YAML block list item continuation (indented "- value")
        if pending_key is not None and re.match(r"^\s+-\s", line):
            pending_items.append(line.strip().lstrip("-").strip())
            continue
        # Any non-list line flushes the pending list
        _flush()
        pending_key = None
        pending_items = []
        if ":" in line and not line.startswith(" "):
            key, _, val = line.partition(":")
            val = val.strip().strip('"')
            if val:
                fields[key.strip()] = val
            else:
                # No inline value — may be followed by block list items
                pending_key = key.strip()
    else:
        _flush()

    return fields


def _parse_list_field(raw: str) -> list[str]:
    """Parse a frontmatter list value like '[REQ-001, REQ-002]' into ids."""
    return [tok.strip().strip('"\'') for tok in re.split(r"[,\[\]\s]+", raw) if tok.strip().strip('"\'')]


def check_depends(path: Path) -> list[str]:
    """Return a list of unsatisfied dependency ids (empty = all clear).

    Mirrors the logic in harness.sh::check_depends:
    - dep in archive/done/           → satisfied
    - dep in archive/cancelled/      → blocked (needs human decision)
    - dep file exists with done/closed status → satisfied
    - dep file exists with any other status   → blocked (dep still open)
    - dep file not found anywhere            → blocked (unknown)
    """
    fm = parse_frontmatter(path)
    raw = fm.get("depends_on", "")
    deps = _parse_list_field(raw)
    if not deps:
        return []

    blocked: list[str] = []
    for dep in deps:
        # Archive/done → satisfied regardless of type
        if list(ARCHIVE_DONE.glob(f"{dep}.md")):
            continue
        # Archive/cancelled → human decision needed
        if list(ARCHIVE_CANCELLED.glob(f"{dep}.md")):
            blocked.append(f"{dep}(cancelled)")
            continue
        # Live REQ file
        req_file = FEATURES_DIR / f"{dep}.md"
        if req_file.exists():
            status = parse_frontmatter(req_file).get("status", "")
            if status in _REQ_DONE_STATUSES:
                continue
            blocked.append(f"{dep}({status or 'unknown'})")
            continue
        # Live BUG file
        bug_file = BUGS_DIR / f"{dep}.md"
        if bug_file.exists():
            status = parse_frontmatter(bug_file).get("status", "")
            if status in _BUG_DONE_STATUSES:
                continue
            blocked.append(f"{dep}({status or 'unknown'})")
            continue
        # Not found anywhere
        blocked.append(f"{dep}(not_found)")

    return blocked


def scan_tc_design() -> tuple[list[dict], list[dict]]:
    """Pass 1: ready, unassigned, no TCs, depends_on satisfied.

    Returns (claimable, blocked) lists.
    """
    claimable: list[dict] = []
    blocked: list[dict] = []
    for f in sorted(FEATURES_DIR.glob("*.md")):
        fm = parse_frontmatter(f)
        if not (
            fm.get("status") == "ready"
            and fm.get("owner", "unassigned") == "unassigned"
            and not _parse_list_field(fm.get("test_case_ref", ""))
        ):
            continue
        entry = {"id": fm.get("req_id", f.stem), "title": fm.get("title", ""), "file": f.name}
        unsatisfied = check_depends(f)
        if unsatisfied:
            entry["blocked_by"] = unsatisfied
            blocked.append(entry)
        else:
            claimable.append(entry)
    return claimable, blocked


def scan_implement() -> tuple[list[dict], list[dict]]:
    """Pass 2: test_designed, unassigned, depends_on satisfied.

    Returns (claimable, blocked) lists.
    """
    claimable: list[dict] = []
    blocked: list[dict] = []
    for f in sorted(FEATURES_DIR.glob("*.md")):
        fm = parse_frontmatter(f)
        if not (fm.get("status") == "test_designed" and fm.get("owner", "unassigned") == "unassigned"):
            continue
        entry = {"id": fm.get("req_id", f.stem), "title": fm.get("title", ""), "file": f.name}
        unsatisfied = check_depends(f)
        if unsatisfied:
            entry["blocked_by"] = unsatisfied
            blocked.append(entry)
        else:
            claimable.append(entry)
    return claimable, blocked


def main() -> int:
    if not FEATURES_DIR.is_dir():
        print("tasks/features/ not found — nothing to scan", file=sys.stderr)
        return 1

    tc_claimable, tc_blocked = scan_tc_design()
    impl_claimable, impl_blocked = scan_implement()

    print("=== agent-loop scan ===")

    print(f"\nPass 1 — TC design claimable (status=ready, unassigned, no TCs, deps done): {len(tc_claimable)}")
    for t in tc_claimable:
        print(f"  {t['id']:12s}  {t['title']}")
    if tc_blocked:
        print(f"  (blocked by depends_on: {len(tc_blocked)})")
        for t in tc_blocked:
            print(f"    {t['id']:12s}  {t['title']}  blocked_by={t['blocked_by']}")

    print(f"\nPass 2 — Implementation claimable (status=test_designed, unassigned, deps done): {len(impl_claimable)}")
    for t in impl_claimable:
        print(f"  {t['id']:12s}  {t['title']}")
    if impl_blocked:
        print(f"  (blocked by depends_on: {len(impl_blocked)})")
        for t in impl_blocked:
            print(f"    {t['id']:12s}  {t['title']}  blocked_by={t['blocked_by']}")

    total = len(tc_claimable) + len(impl_claimable)
    print(f"\nTotal claimable: {total}")
    if total > 0:
        print("To trigger agents manually:")
        for t in tc_claimable:
            print(f"  ./scripts/harness.sh tc-design {t['id']}")
        for t in impl_claimable:
            print(f"  ./scripts/harness.sh implement {t['id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
