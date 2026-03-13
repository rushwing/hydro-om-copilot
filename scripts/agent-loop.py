#!/usr/bin/env python3
"""
agent-loop.py — Git-Native Agent Loop stub

Scans tasks/ for claimable work items and prints a summary.
Intended to be run by GitHub Actions after each PR merge to main.

Current status: stub — prints claimable tasks only.
Actual agent invocation (harness.sh tc-design / implement) is triggered
manually until the loop is proven stable.

Two-pass scan (see harness/harness-index.md §自动化流程):
  Pass 1 — TC design:     status=ready, owner=unassigned, test_case_ref empty
  Pass 2 — Implementation: status=test_designed, owner=unassigned
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FEATURES_DIR = REPO_ROOT / "tasks" / "features"


def parse_frontmatter(path: Path) -> dict:
    """Extract key: value pairs from YAML frontmatter (--- delimited)."""
    fields: dict = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return fields
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return fields
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, _, val = line.partition(":")
            fields[key.strip()] = val.strip().strip('"')
    return fields


def scan_tc_design() -> list[dict]:
    """Pass 1: ready, unassigned, no TCs yet."""
    results = []
    for f in sorted(FEATURES_DIR.glob("*.md")):
        fm = parse_frontmatter(f)
        if (
            fm.get("status") == "ready"
            and fm.get("owner", "unassigned") == "unassigned"
            and not fm.get("test_case_ref", "").strip("[] ")
        ):
            results.append({"id": fm.get("req_id", f.stem), "title": fm.get("title", ""), "file": f.name})
    return results


def scan_implement() -> list[dict]:
    """Pass 2: test_designed, unassigned."""
    results = []
    for f in sorted(FEATURES_DIR.glob("*.md")):
        fm = parse_frontmatter(f)
        if fm.get("status") == "test_designed" and fm.get("owner", "unassigned") == "unassigned":
            results.append({"id": fm.get("req_id", f.stem), "title": fm.get("title", ""), "file": f.name})
    return results


def main() -> int:
    if not FEATURES_DIR.is_dir():
        print("tasks/features/ not found — nothing to scan", file=sys.stderr)
        return 1

    tc_tasks = scan_tc_design()
    impl_tasks = scan_implement()

    print("=== agent-loop scan ===")
    print(f"\nPass 1 — TC design candidates (status=ready, unassigned, no TCs): {len(tc_tasks)}")
    for t in tc_tasks:
        print(f"  {t['id']:12s}  {t['title']}")

    print(f"\nPass 2 — Implementation candidates (status=test_designed, unassigned): {len(impl_tasks)}")
    for t in impl_tasks:
        print(f"  {t['id']:12s}  {t['title']}")

    total = len(tc_tasks) + len(impl_tasks)
    print(f"\nTotal claimable: {total}")
    if total > 0:
        print("To trigger agents manually:")
        for t in tc_tasks:
            print(f"  ./scripts/harness.sh tc-design {t['id']}")
        for t in impl_tasks:
            print(f"  ./scripts/harness.sh implement {t['id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
