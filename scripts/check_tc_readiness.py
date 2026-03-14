#!/usr/bin/env python3
"""
TC Readiness Scanner — TC 就绪性与 tc_policy 门禁校验

检查四类问题：
  A. REQ policy  : tc_policy=required 的 REQ 在高阶状态时必须有 test_case_ref
  B. BUG policy  : tc_policy=required 的 BUG 在实现状态时必须有 related_tc
  C. TC 引用存在性: test_case_ref / related_tc 中的 TC ID 必须能在 tasks/test-cases/ 或
                   tasks/archive/done/ 找到对应文件
  D. TC frontmatter: TC 文档本身的必填字段、status 枚举、以及 passed/implemented 状态下
                     spec_file / spec_name 非空

Usage:
    python3 scripts/check_tc_readiness.py           # 报告模式
    python3 scripts/check_tc_readiness.py --strict  # CI 模式（有错误 exit 1）
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).parent.parent

# ─── 颜色 ─────────────────────────────────────────────────────────────────────

BOLD  = "\033[1m"
RED   = "\033[31m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
CYAN  = "\033[36m"
RESET = "\033[0m"


def _section(title: str) -> str:
    return f"\n{BOLD}{CYAN}{'─'*4} {title} {'─'*(50 - len(title))}{RESET}"


# ─── 常量 ─────────────────────────────────────────────────────────────────────

# REQ statuses that require tc_policy=required to have test_case_ref filled
REQ_ACTIVE_STATUSES = {"test_designed", "in_progress", "review", "done"}

# BUG statuses that require tc_policy=required to have related_tc filled
BUG_ACTIVE_STATUSES = {"in_progress", "fixed", "regressing", "closed"}

VALID_TC_POLICY = {"required", "optional", "exempt"}

TC_REQUIRED_FIELDS = {"tc_id", "title", "status", "layer", "priority"}
TC_VALID_STATUSES  = {"passed", "planned", "draft", "blocked", "implemented"}
TC_SPEC_STATUSES   = {"passed", "implemented"}  # must have spec_file + spec_name


# ─── frontmatter 解析 ─────────────────────────────────────────────────────────

def _parse_frontmatter(text: str) -> dict[str, str]:
    """Extract YAML-ish frontmatter between --- delimiters.

    Supports inline values and YAML block lists.
    Block list values are stored as '[item1, item2]'.
    """
    lines = text.splitlines()
    in_fm = False
    fm: dict[str, str] = {}
    pending_key: str | None = None
    pending_items: list[str] = []

    def _flush() -> None:
        if pending_key is not None:
            fm[pending_key] = "[" + ", ".join(pending_items) + "]"

    for line in lines:
        if line.strip() == "---":
            if not in_fm:
                in_fm = True
                continue
            else:
                _flush()
                break
        if not in_fm:
            continue
        if pending_key is not None and re.match(r"^\s+-\s", line):
            pending_items.append(line.strip().lstrip("-").strip())
            continue
        _flush()
        pending_key = None
        pending_items = []
        if ":" in line and not line.startswith(" "):
            key, _, val = line.partition(":")
            val = val.strip()
            if val:
                fm[key.strip()] = val
            else:
                pending_key = key.strip()
    else:
        _flush()

    return fm


def _parse_id_list(raw: str) -> list[str]:
    """Parse a frontmatter list value like '[TC-001, TC-E2E-002]' into IDs."""
    return [s.strip() for s in re.split(r"[,\[\]\s]+", raw) if s.strip()]


# ─── 数据结构 ─────────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    errors:   list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


# ─── TC 文件索引 ──────────────────────────────────────────────────────────────

def _build_tc_index() -> dict[str, Path]:
    """Return mapping tc_id -> file path for all TC-*.md files."""
    index: dict[str, Path] = {}
    search_dirs = [
        ROOT / "tasks" / "test-cases",
        ROOT / "tasks" / "archive" / "done",
    ]
    for d in search_dirs:
        if not d.exists():
            continue
        for p in d.glob("TC-*.md"):
            # Extract TC ID from frontmatter or filename prefix
            try:
                text = p.read_text(encoding="utf-8")
                fm = _parse_frontmatter(text)
                tc_id = fm.get("tc_id", "").strip()
            except Exception:
                tc_id = ""
            if not tc_id:
                # Fallback: parse from filename (TC-E2E-001-xxx.md → TC-E2E-001)
                m = re.match(r"(TC-[A-Z0-9]+-\d+)", p.stem)
                if m:
                    tc_id = m.group(1)
            if tc_id:
                index[tc_id] = p
    return index


# ─── A. REQ policy 检查 ───────────────────────────────────────────────────────

def check_req_policy(result: CheckResult) -> None:
    """Scan REQ-*.md in features/ and archive/done/ for tc_policy violations."""
    search_dirs = [
        ROOT / "tasks" / "features",
        ROOT / "tasks" / "archive" / "done",
    ]
    for d in search_dirs:
        if not d.exists():
            continue
        for path in sorted(d.glob("REQ-*.md")):
            try:
                text = path.read_text(encoding="utf-8")
            except Exception as e:
                result.error(f"{path.name}: 读取失败 — {e}")
                continue

            fm = _parse_frontmatter(text)
            tc_policy = fm.get("tc_policy", "").strip()
            status    = fm.get("status", "").strip()

            # tc_policy enum validation (only when field is present)
            if tc_policy and tc_policy not in VALID_TC_POLICY:
                result.error(
                    f"{path.name}: tc_policy='{tc_policy}' 非法，"
                    f"允许值: {sorted(VALID_TC_POLICY)}"
                )

            # tc_policy=exempt → tc_exempt_reason must be non-empty
            if tc_policy == "exempt":
                reason = fm.get("tc_exempt_reason", "").strip().strip('"')
                if not reason:
                    result.error(
                        f"{path.name}: tc_policy=exempt 但 tc_exempt_reason 为空"
                    )

            # tc_policy=required + active status → test_case_ref must be non-empty
            if tc_policy == "required" and status in REQ_ACTIVE_STATUSES:
                raw_ref = fm.get("test_case_ref", "[]")
                refs = _parse_id_list(raw_ref)
                if not refs:
                    result.error(
                        f"{path.name}: tc_policy=required, status={status} "
                        f"但 test_case_ref 为空"
                    )


# ─── B. BUG policy 检查 ───────────────────────────────────────────────────────

def check_bug_policy(result: CheckResult) -> None:
    """Scan BUG-*.md in bugs/ and archive/done/ for tc_policy violations."""
    search_dirs = [
        ROOT / "tasks" / "bugs",
        ROOT / "tasks" / "archive" / "done",
    ]
    for d in search_dirs:
        if not d.exists():
            continue
        for path in sorted(d.glob("BUG-*.md")):
            try:
                text = path.read_text(encoding="utf-8")
            except Exception as e:
                result.error(f"{path.name}: 读取失败 — {e}")
                continue

            fm = _parse_frontmatter(text)
            tc_policy = fm.get("tc_policy", "").strip()
            status    = fm.get("status", "").strip()

            # tc_policy enum validation
            if tc_policy and tc_policy not in VALID_TC_POLICY:
                result.error(
                    f"{path.name}: tc_policy='{tc_policy}' 非法，"
                    f"允许值: {sorted(VALID_TC_POLICY)}"
                )

            # tc_policy=exempt → tc_exempt_reason must be non-empty
            if tc_policy == "exempt":
                reason = fm.get("tc_exempt_reason", "").strip().strip('"')
                if not reason:
                    result.error(
                        f"{path.name}: tc_policy=exempt 但 tc_exempt_reason 为空"
                    )

            # tc_policy=required + active status → related_tc must be non-empty
            if tc_policy == "required" and status in BUG_ACTIVE_STATUSES:
                raw_ref = fm.get("related_tc", "[]")
                refs = _parse_id_list(raw_ref)
                if not refs:
                    result.error(
                        f"{path.name}: tc_policy=required, status={status} "
                        f"但 related_tc 为空"
                    )


# ─── C. TC 引用存在性检查 ─────────────────────────────────────────────────────

def check_tc_refs(result: CheckResult, tc_index: dict[str, Path]) -> None:
    """Verify all TC IDs referenced in REQ/BUG docs exist in the TC index."""
    search_dirs_req = [
        ROOT / "tasks" / "features",
        ROOT / "tasks" / "archive" / "done",
    ]
    search_dirs_bug = [
        ROOT / "tasks" / "bugs",
        ROOT / "tasks" / "archive" / "done",
    ]

    def _check_refs(dirs: list[Path], glob: str, field_name: str) -> None:
        for d in dirs:
            if not d.exists():
                continue
            for path in sorted(d.glob(glob)):
                try:
                    text = path.read_text(encoding="utf-8")
                except Exception:
                    continue
                fm = _parse_frontmatter(text)
                raw = fm.get(field_name, "[]")
                refs = _parse_id_list(raw)
                for tc_id in refs:
                    if not tc_id.startswith("TC-"):
                        continue
                    if tc_id not in tc_index:
                        result.error(
                            f"{path.name}: {field_name} 引用 {tc_id} 不存在于 "
                            f"tasks/test-cases/ 或 tasks/archive/done/"
                        )

    _check_refs(search_dirs_req, "REQ-*.md", "test_case_ref")
    _check_refs(search_dirs_bug, "BUG-*.md", "related_tc")


# ─── D. TC frontmatter 检查 ───────────────────────────────────────────────────

def check_tc_frontmatter(result: CheckResult) -> None:
    """Validate frontmatter of all TC-*.md in tasks/test-cases/."""
    tc_dir = ROOT / "tasks" / "test-cases"
    if not tc_dir.exists():
        return

    for path in sorted(tc_dir.glob("TC-*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:
            result.error(f"{path.name}: 读取失败 — {e}")
            continue

        fm = _parse_frontmatter(text)

        # Required fields
        missing = [f for f in TC_REQUIRED_FIELDS if f not in fm]
        if missing:
            result.error(f"{path.name}: 缺少必填字段: {', '.join(missing)}")

        # Must have req_ref or bug_ref
        has_req_ref = bool(fm.get("req_ref", "").strip().strip("[]").strip())
        has_bug_ref = bool(fm.get("bug_ref", "").strip().strip("[]").strip())
        if not has_req_ref and not has_bug_ref:
            result.error(f"{path.name}: 缺少 req_ref 或 bug_ref（至少填一个）")

        # status enum
        tc_status = fm.get("status", "").strip()
        if tc_status and tc_status not in TC_VALID_STATUSES:
            result.error(
                f"{path.name}: status='{tc_status}' 非法，"
                f"允许值: {sorted(TC_VALID_STATUSES)}"
            )

        # passed/implemented → spec_file and spec_name must be non-empty
        if tc_status in TC_SPEC_STATUSES:
            spec_file = fm.get("spec_file", "").strip().strip('"')
            spec_name = fm.get("spec_name", "").strip().strip('"')
            if not spec_file:
                result.error(
                    f"{path.name}: status={tc_status} 但 spec_file 为空"
                )
            if not spec_name:
                result.error(
                    f"{path.name}: status={tc_status} 但 spec_name 为空"
                )


# ─── E. tc_policy 逐步还账检查 ───────────────────────────────────────────────

# BUG statuses that trigger the backfill obligation
# (open/confirmed are pre-claim; debt must be paid once work starts)
BUG_BACKFILL_TRIGGER_STATUSES = {"in_progress", "fixed", "regressing", "closed"}

def _build_req_index() -> dict[str, dict[str, str]]:
    """Return mapping req_id -> frontmatter dict for all REQ-*.md files."""
    index: dict[str, dict[str, str]] = {}
    search_dirs = [
        ROOT / "tasks" / "features",
        ROOT / "tasks" / "archive" / "done",
        ROOT / "tasks" / "archive" / "cancelled",
    ]
    for d in search_dirs:
        if not d.exists():
            continue
        for path in sorted(d.glob("REQ-*.md")):
            try:
                text = path.read_text(encoding="utf-8")
                fm = _parse_frontmatter(text)
                req_id = fm.get("req_id", "").strip()
                if req_id:
                    index[req_id] = fm
            except Exception:
                pass
    return index


def check_backfill(result: CheckResult, req_index: dict[str, dict[str, str]]) -> None:
    """E. Verify that active BUGs have triggered tc_policy backfill on related REQs.

    Per bug-standard.md §2.1: when a BUG references a REQ that has no tc_policy
    field (or tc_policy=optional), opening the BUG must also backfill that REQ
    to tc_policy=required (or exempt with reason).

    We enforce this once the BUG enters an active fix status (in_progress+), so
    that open/confirmed BUGs don't immediately block before the developer starts.
    """
    search_dirs = [
        ROOT / "tasks" / "bugs",
        ROOT / "tasks" / "archive" / "done",
    ]
    for d in search_dirs:
        if not d.exists():
            continue
        for path in sorted(d.glob("BUG-*.md")):
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue

            fm = _parse_frontmatter(text)
            status = fm.get("status", "").strip()

            # Only enforce once the fix is actively in progress
            if status not in BUG_BACKFILL_TRIGGER_STATUSES:
                continue

            raw_related = fm.get("related_req", "[]")
            related_reqs = [
                r for r in _parse_id_list(raw_related) if r.startswith("REQ-")
            ]

            for req_id in related_reqs:
                req_fm = req_index.get(req_id)
                if req_fm is None:
                    # REQ not found — already caught by check_bug_frontmatter
                    continue
                req_tc_policy = req_fm.get("tc_policy", "").strip()
                # Debt is unpaid if field is absent or explicitly optional
                if req_tc_policy in ("", "optional"):
                    result.error(
                        f"{path.name} (status={status}): related_req {req_id} 的 "
                        f"tc_policy 未回填（当前='{req_tc_policy or '缺失'}'）。"
                        f"按 bug-standard.md §2.1，认领修复时须将 {req_id} 的 "
                        f"tc_policy 改为 required（或 exempt+理由）。"
                    )


# ─── 报告输出 ─────────────────────────────────────────────────────────────────

def print_report(result: CheckResult) -> int:
    print(f"\n{BOLD}TC Readiness Scanner{RESET}")

    if result.errors:
        print(_section(f"错误  {RED}[{len(result.errors)}]{RESET}"))
        for e in result.errors:
            print(f"  {RED}✗{RESET} {e}")

    if result.warnings:
        print(_section(f"警告  {YELLOW}[{len(result.warnings)}]{RESET}"))
        for w in result.warnings:
            print(f"  {YELLOW}!{RESET} {w}")

    print(f"\n{'─'*60}")
    if not result.errors:
        print(f"{GREEN}{BOLD}✓ TC 就绪性检查全部通过{RESET}")
        return 0
    else:
        print(f"{RED}{BOLD}✗ 发现 {len(result.errors)} 处错误，见上方报告{RESET}")
        return 1


# ─── 入口 ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="TC readiness scanner")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="有错误时 exit(1)，用于 CI",
    )
    args = parser.parse_args()

    tc_index  = _build_tc_index()
    req_index = _build_req_index()

    result = CheckResult()
    check_req_policy(result)
    check_bug_policy(result)
    check_tc_refs(result, tc_index)
    check_tc_frontmatter(result)
    check_backfill(result, req_index)

    exit_code = print_report(result)

    if args.strict:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
