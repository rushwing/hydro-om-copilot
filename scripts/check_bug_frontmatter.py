#!/usr/bin/env python3
"""
BUG Frontmatter Validator — tasks/bugs/BUG-*.md 合规检查

校验内容（对应 harness/bug-standard.md §9 自动可检查项）：
  1. 必填字段存在性
  2. status 枚举合法性
  3. severity 枚举合法性（S1/S2/S3/S4）
  4. priority 枚举合法性（P0/P1/P2/P3）
  5. status == fixed 时 related_tc 非空
  6. status == in_progress 时 owner != unassigned
  7. related_req 中每个 ID 在 tasks/ 目录中存在
  8. depends_on 中每个 ID 在 tasks/ 目录中存在

Usage:
    python3 scripts/check_bug_frontmatter.py           # 报告模式
    python3 scripts/check_bug_frontmatter.py --strict  # CI 模式（有错误时 exit 1）
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

BUGS_DIR = ROOT / "tasks" / "bugs"
TASKS_DIRS = [
    ROOT / "tasks" / "features",
    ROOT / "tasks" / "bugs",
    ROOT / "tasks" / "archive" / "done",
    ROOT / "tasks" / "archive" / "cancelled",
]

REQUIRED_FIELDS = [
    "bug_id",
    "title",
    "status",
    "severity",
    "priority",
    "owner",
    "related_req",
    "related_tc",
    "reported_by",
]

VALID_STATUS = {"open", "confirmed", "in_progress", "fixed", "regressing", "closed", "wont_fix"}
VALID_SEVERITY = {"S1", "S2", "S3", "S4"}
VALID_PRIORITY = {"P0", "P1", "P2", "P3"}


def _parse_frontmatter(path: Path) -> dict | None:
    """Extract YAML frontmatter fields as raw strings. Returns None if no frontmatter."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return None
    fields: dict = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        fields[key.strip()] = val.strip()
    return fields


def _parse_list_field(raw: str) -> list[str]:
    """Parse a YAML inline list like '[REQ-001, BUG-002]' or '[]'."""
    inner = raw.strip().lstrip("[").rstrip("]")
    if not inner:
        return []
    return [item.strip() for item in inner.split(",") if item.strip()]


def _build_known_ids() -> set[str]:
    """Collect all REQ-xxx and BUG-xxx IDs from tasks/ directories."""
    known: set[str] = set()
    for d in TASKS_DIRS:
        if not d.exists():
            continue
        for f in d.glob("*.md"):
            m = re.match(r"^(REQ-\d+|BUG-\d+)\.md$", f.name)
            if m:
                known.add(m.group(1))
    return known


def validate_bug(path: Path, known_ids: set[str]) -> list[str]:
    """Return list of error strings for a single BUG file."""
    errors: list[str] = []
    fm = _parse_frontmatter(path)

    if fm is None:
        return [f"{path.name}: missing frontmatter block"]

    # 1. Required fields
    for field in REQUIRED_FIELDS:
        if field not in fm:
            errors.append(f"{path.name}: missing required field '{field}'")

    if errors:
        # Can't do further checks without basic fields
        return errors

    # 2. status enum
    status = fm["status"]
    if status not in VALID_STATUS:
        errors.append(
            f"{path.name}: invalid status '{status}' (allowed: {sorted(VALID_STATUS)})"
        )

    # 3. severity enum
    severity = fm["severity"]
    if severity not in VALID_SEVERITY:
        errors.append(
            f"{path.name}: invalid severity '{severity}' (allowed: {sorted(VALID_SEVERITY)})"
        )

    # 4. priority enum
    priority = fm["priority"]
    if priority not in VALID_PRIORITY:
        errors.append(
            f"{path.name}: invalid priority '{priority}' (allowed: {sorted(VALID_PRIORITY)})"
        )

    # 5. status == fixed → related_tc non-empty
    related_tc = _parse_list_field(fm.get("related_tc", "[]"))
    if status == "fixed" and not related_tc:
        errors.append(f"{path.name}: status is 'fixed' but related_tc is empty")

    # 6. status == in_progress → owner != unassigned
    owner = fm.get("owner", "unassigned")
    if status == "in_progress" and owner == "unassigned":
        errors.append(f"{path.name}: status is 'in_progress' but owner is 'unassigned'")

    # 7. related_req IDs must exist in tasks/
    related_req = _parse_list_field(fm.get("related_req", "[]"))
    for req_id in related_req:
        if not re.match(r"^REQ-\d+$", req_id):
            errors.append(f"{path.name}: related_req entry '{req_id}' is not a valid REQ-ID")
        elif req_id not in known_ids:
            errors.append(f"{path.name}: related_req '{req_id}' not found in tasks/")

    # 8. depends_on IDs must exist in tasks/
    depends_on = _parse_list_field(fm.get("depends_on", "[]"))
    for dep_id in depends_on:
        if not re.match(r"^(REQ|BUG)-\d+$", dep_id):
            errors.append(f"{path.name}: depends_on entry '{dep_id}' is not a valid REQ/BUG ID")
        elif dep_id not in known_ids:
            errors.append(f"{path.name}: depends_on '{dep_id}' not found in tasks/")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate BUG frontmatter files")
    parser.add_argument("--strict", action="store_true", help="Exit 1 if any errors found")
    args = parser.parse_args()

    if not BUGS_DIR.exists():
        print("tasks/bugs/ does not exist — nothing to validate")
        return 0

    bug_files = sorted(BUGS_DIR.glob("BUG-*.md"))
    if not bug_files:
        print("No BUG-*.md files found in tasks/bugs/ — OK")
        return 0

    known_ids = _build_known_ids()
    all_errors: list[str] = []

    for path in bug_files:
        errs = validate_bug(path, known_ids)
        all_errors.extend(errs)

    if all_errors:
        print(f"BUG frontmatter validation FAILED ({len(all_errors)} error(s)):\n")
        for err in all_errors:
            print(f"  ✗ {err}")
        print()
        if args.strict:
            return 1
    else:
        print(f"BUG frontmatter validation passed ({len(bug_files)} file(s) checked)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
