#!/usr/bin/env python3
"""
REQ Coverage Scanner — 双向需求完备性检查

两个方向同时扫描：
  Code → REQ : 已实现的 artifact 是否都有对应 REQ（孤儿检测）
  REQ → Code : done 状态的 REQ 是否有可找到的对应实现（幽灵检测）

Usage:
    python scripts/check_req_coverage.py           # 正常报告
    python scripts/check_req_coverage.py --verbose # 显示所有匹配明细
    python scripts/check_req_coverage.py --strict  # 有任意缺口时 exit(1)，用于 CI
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ─── 项目根目录 ───────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent

# ─── 数据结构 ─────────────────────────────────────────────────────────────────


@dataclass
class ReqDoc:
    req_id: str
    title: str
    status: str
    scope: str
    acceptance: str
    phase: str
    priority: str
    depends_on: list[str]
    body: str  # full file content (for keyword search)
    path: Path
    code_refs: list[str] = field(default_factory=list)  # explicit file paths from Agent Notes


@dataclass
class CodeArtifact:
    kind: str       # route | component | node | mcp_tool
    name: str       # human-readable name, e.g. "POST /diagnosis/run"
    file: Path
    line: int
    matched_req: str | None = None  # filled during matching


@dataclass
class ScanResult:
    reqs: list[ReqDoc] = field(default_factory=list)
    artifacts: list[CodeArtifact] = field(default_factory=list)
    orphan_artifacts: list[CodeArtifact] = field(default_factory=list)   # no REQ
    ghost_reqs: list[ReqDoc] = field(default_factory=list)               # done but no artifact
    frontmatter_errors: list[str] = field(default_factory=list)
    dep_errors: list[str] = field(default_factory=list)
    status_errors: list[str] = field(default_factory=list)


# ─── REQ 解析 ─────────────────────────────────────────────────────────────────

REQUIRED_FIELDS = [
    "req_id", "title", "status", "priority", "phase",
    "owner", "depends_on", "test_case_ref", "scope", "acceptance",
]

VALID_STATUSES = {"draft", "ready", "test_designed", "in_progress", "blocked", "review", "done"}
VALID_SCOPES = {"frontend", "backend", "fullstack", "docs", "tests"}
VALID_PRIORITIES = {"P0", "P1", "P2", "P3"}


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Extract YAML-ish frontmatter between --- delimiters.

    Supports both inline values  (key: value)
    and YAML block lists          (key:\n  - item1\n  - item2).
    Block list values are stored as '[item1, item2]' so that downstream
    consumers (re.findall, split) can consume them without changes.
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
            val = val.strip()
            if val:
                fm[key.strip()] = val
            else:
                pending_key = key.strip()
    else:
        _flush()

    return fm


def load_reqs(result: ScanResult) -> None:
    task_dirs = [
        ROOT / "tasks" / "features",
        ROOT / "tasks" / "archive" / "done",
        ROOT / "tasks" / "archive" / "cancelled",
    ]
    all_req_ids: set[str] = set()

    for task_dir in task_dirs:
        if not task_dir.exists():
            continue
        for path in sorted(task_dir.glob("REQ-*.md")):
            text = path.read_text(encoding="utf-8")
            fm = _parse_frontmatter(text)

            # ── Frontmatter completeness ──────────────────────────────────
            missing = [f for f in REQUIRED_FIELDS if f not in fm]
            if missing:
                result.frontmatter_errors.append(
                    f"{path.name}: missing fields: {', '.join(missing)}"
                )
                continue  # can't build ReqDoc without required fields

            req_id = fm["req_id"]
            all_req_ids.add(req_id)

            # ── Enum validation ───────────────────────────────────────────
            if fm["status"] not in VALID_STATUSES:
                result.status_errors.append(
                    f"{path.name}: invalid status '{fm['status']}'"
                )
            if fm["scope"] not in VALID_SCOPES:
                result.status_errors.append(
                    f"{path.name}: invalid scope '{fm['scope']}'"
                )
            if fm["priority"] not in VALID_PRIORITIES:
                result.status_errors.append(
                    f"{path.name}: invalid priority '{fm['priority']}'"
                )

            # ── depends_on parse ──────────────────────────────────────────
            raw_deps = fm.get("depends_on", "[]")
            dep_ids = re.findall(r"REQ-\d+", raw_deps)

            # ── code_refs parse (from Agent Notes block) ──────────────
            code_refs: list[str] = []
            in_refs = False
            for line in text.splitlines():
                if re.match(r"\s*code_refs\s*:", line):
                    in_refs = True
                    continue
                if in_refs:
                    m = re.match(r"\s+-\s+([\w/.\-]+)", line)
                    if m:
                        code_refs.append(m.group(1))
                    elif line.strip() and not line.strip().startswith("#"):
                        in_refs = False  # end of block

            doc = ReqDoc(
                req_id=req_id,
                title=fm["title"],
                status=fm["status"],
                scope=fm["scope"],
                acceptance=fm["acceptance"],
                phase=fm["phase"],
                priority=fm["priority"],
                depends_on=dep_ids,
                body=text,
                path=path,
                code_refs=code_refs,
            )
            result.reqs.append(doc)

    # ── Dependency reference integrity ────────────────────────────────────
    for doc in result.reqs:
        for dep in doc.depends_on:
            if dep not in all_req_ids:
                result.dep_errors.append(
                    f"{doc.req_id}: depends_on '{dep}' not found in tasks/"
                )


# ─── Code Artifact 提取 ───────────────────────────────────────────────────────


_EXCLUDE_DIRS = {".venv", "node_modules", "__pycache__", ".git", "site-packages"}


def _py_files(directory: Path):
    """Yield .py files, skipping virtual-env and cache directories."""
    for path in directory.rglob("*.py"):
        if not any(part in _EXCLUDE_DIRS for part in path.parts):
            yield path


def _tsx_files(directory: Path):
    """Yield .tsx files, skipping node_modules."""
    for path in directory.rglob("*.tsx"):
        if not any(part in _EXCLUDE_DIRS for part in path.parts):
            yield path


def _extract_routes(result: ScanResult) -> None:
    """Scan FastAPI route decorators in backend/, prepending APIRouter prefix."""
    route_re = re.compile(
        r'@\w+\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
        re.IGNORECASE,
    )
    # Matches: APIRouter(prefix="/some/path", ...) or APIRouter(prefix='/some/path', ...)
    prefix_re = re.compile(r'APIRouter\s*\([^)]*prefix\s*=\s*["\']([^"\']*)["\']')

    for path in _py_files(ROOT / "backend"):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        # Extract router-level prefix declared in this file (empty string if none)
        prefix_match = prefix_re.search(text)
        router_prefix = prefix_match.group(1).rstrip("/") if prefix_match else ""

        for m in route_re.finditer(text):
            method = m.group(1).upper()
            decorator_path = m.group(2)
            # Compose full public path: prefix + decorator path
            full_path = router_prefix + "/" + decorator_path.lstrip("/") if router_prefix else decorator_path
            lineno = text[: m.start()].count("\n") + 1
            result.artifacts.append(
                CodeArtifact(
                    kind="route",
                    name=f"{method} {full_path}",
                    file=path.relative_to(ROOT),
                    line=lineno,
                )
            )


def _extract_components(result: ScanResult) -> None:
    """Scan exported React components in frontend/src/"""
    comp_re = re.compile(
        r"export\s+(?:default\s+)?(?:function|const|class)\s+([A-Z][A-Za-z0-9]+)"
    )
    for path in _tsx_files(ROOT / "frontend" / "src"):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for m in comp_re.finditer(text):
            name = m.group(1)
            lineno = text[: m.start()].count("\n") + 1
            result.artifacts.append(
                CodeArtifact(
                    kind="component",
                    name=name,
                    file=path.relative_to(ROOT),
                    line=lineno,
                )
            )


def _extract_langgraph_nodes(result: ScanResult) -> None:
    """Scan graph.add_node() calls in backend/"""
    node_re = re.compile(r'(?:graph|workflow|builder)\.add_node\s*\(\s*["\']([^"\']+)["\']')
    for path in _py_files(ROOT / "backend"):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for m in node_re.finditer(text):
            name = m.group(1)
            lineno = text[: m.start()].count("\n") + 1
            result.artifacts.append(
                CodeArtifact(
                    kind="node",
                    name=f"node:{name}",
                    file=path.relative_to(ROOT),
                    line=lineno,
                )
            )


def _extract_mcp_tools(result: ScanResult) -> None:
    """Scan @mcp.tool decorated functions in backend/mcp_servers/"""
    tool_re = re.compile(r"@\w+\.tool[^\n]*\n\s*(?:async\s+)?def\s+(\w+)")
    for path in _py_files(ROOT / "backend" / "mcp_servers"):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for m in tool_re.finditer(text):
            name = m.group(1)
            lineno = text[: m.start()].count("\n") + 1
            result.artifacts.append(
                CodeArtifact(
                    kind="mcp_tool",
                    name=f"tool:{name}",
                    file=path.relative_to(ROOT),
                    line=lineno,
                )
            )


def extract_artifacts(result: ScanResult) -> None:
    _extract_routes(result)
    _extract_components(result)
    _extract_langgraph_nodes(result)
    _extract_mcp_tools(result)


# ─── 双向匹配 ─────────────────────────────────────────────────────────────────

# 只考虑 done/review/in_progress 的 REQ 有对应实现；draft 不做 ghost 检查
_IMPL_STATUSES = {"done", "review", "in_progress"}

# 小词（出现在路径/名称但语义太宽泛）不单独作为匹配 token
_STOPWORDS = {"the", "a", "an", "of", "in", "to", "for", "and", "or", "with"}


def _tokens(text: str) -> set[str]:
    """Tokenize a string into lowercase words, stripping punctuation."""
    return {
        w.lower()
        for w in re.split(r"[\s/\-_.,;(){}[\]\"\']+", text)
        if len(w) > 2 and w.lower() not in _STOPWORDS
    }


def _artifact_matches_req(artifact: CodeArtifact, req: ReqDoc) -> bool:
    """
    Match priority:
    1. code_refs: artifact file path appears in REQ's explicit code_refs list (highest)
    2. Exact substring: artifact name in REQ body
    3. Route path segments: individual segments in REQ body
    4. Token overlap: artifact name tokens ⊆ acceptance tokens (fallback)
    """
    # ── Priority 1: explicit code_refs file match ─────────────────────────
    if req.code_refs:
        artifact_file = str(artifact.file)
        for ref in req.code_refs:
            # Match if the ref is a prefix/suffix of the artifact file path
            if ref in artifact_file or artifact_file.endswith(ref):
                return True
        # If REQ has code_refs, only match via code_refs (skip heuristics).
        # This prevents spurious keyword hits on REQs that have explicit refs.
        return False

    body_lower = req.body.lower()
    acceptance_lower = req.acceptance.lower()

    # ── Priority 2: Exact substring ───────────────────────────────────────
    artifact_lower = artifact.name.lower()
    if artifact_lower in body_lower:
        return True

    # For routes: match path segments individually
    if artifact.kind == "route":
        # e.g. "POST /diagnosis/run" → check "diagnosis/run" in acceptance
        parts = artifact_lower.split(" ", 1)
        if len(parts) == 2:
            path_part = parts[1].lstrip("/")
            if path_part in body_lower:
                return True
            # Also try individual path segments (avoid matching "/" alone)
            segments = [s for s in path_part.split("/") if len(s) > 3]
            if segments and all(s in body_lower for s in segments):
                return True

    # For components: name in acceptance
    if artifact.kind == "component":
        name_lower = artifact.name.lower()
        if name_lower in acceptance_lower:
            return True

    # Token overlap (fallback)
    art_tokens = _tokens(artifact.name)
    acc_tokens = _tokens(req.acceptance)
    if art_tokens and art_tokens.issubset(acc_tokens):
        return True

    return False


def match_artifacts_to_reqs(result: ScanResult) -> None:
    impl_reqs = [r for r in result.reqs if r.status in _IMPL_STATUSES]

    for artifact in result.artifacts:
        matched = None

        # ── Pass 1: code_refs exact match across ALL REQs (highest priority) ──
        # A future REQ may explicitly claim an artifact via code_refs even before
        # it is implemented (e.g., backfilling docs for existing code).
        for req in result.reqs:
            if req.code_refs and _artifact_matches_req(artifact, req):
                matched = req.req_id
                break

        # ── Pass 2: heuristic match restricted to IMPLEMENTED REQs only ───────
        # Draft/ready REQs must NOT compete for existing artifacts via heuristics
        # because their keyword overlap is coincidental, not intentional.
        if matched is None:
            for req in impl_reqs:
                if not req.code_refs and _artifact_matches_req(artifact, req):
                    matched = req.req_id
                    break

        artifact.matched_req = matched
        if matched is None:
            result.orphan_artifacts.append(artifact)

    # Ghost REQ: done REQ whose acceptance criteria has no matched artifact.
    # REQs with explicit code_refs are treated as "code-verified by declaration"
    # and excluded from ghost detection — the author explicitly mapped the file.
    matched_req_ids = {a.matched_req for a in result.artifacts if a.matched_req}
    for req in impl_reqs:
        if req.req_id not in matched_req_ids and not req.code_refs:
            result.ghost_reqs.append(req)


# ─── 报告输出 ─────────────────────────────────────────────────────────────────

BOLD = "\033[1m"
RED = "\033[31m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
CYAN = "\033[36m"
RESET = "\033[0m"


def _section(title: str) -> str:
    return f"\n{BOLD}{CYAN}{'─'*4} {title} {'─'*(50 - len(title))}{RESET}"


def print_report(result: ScanResult, verbose: bool = False) -> int:
    """Print report and return exit code (0=clean, 1=issues found)."""
    issues = 0

    print(f"\n{BOLD}REQ Coverage Scanner{RESET}")
    print(f"  REQ 文档数 : {len(result.reqs)}")
    print(f"  Code artifact 数 : {len(result.artifacts)}")

    # ── Frontmatter errors ────────────────────────────────────────────────
    if result.frontmatter_errors:
        print(_section("Frontmatter 缺字段"))
        for e in result.frontmatter_errors:
            print(f"  {RED}✗{RESET} {e}")
        issues += len(result.frontmatter_errors)

    # ── Status / scope / priority errors ─────────────────────────────────
    if result.status_errors:
        print(_section("枚举值非法"))
        for e in result.status_errors:
            print(f"  {RED}✗{RESET} {e}")
        issues += len(result.status_errors)

    # ── Dependency errors ─────────────────────────────────────────────────
    if result.dep_errors:
        print(_section("depends_on 引用缺失"))
        for e in result.dep_errors:
            print(f"  {RED}✗{RESET} {e}")
        issues += len(result.dep_errors)

    # ── Orphan artifacts (Code → REQ 缺口) ───────────────────────────────
    if result.orphan_artifacts:
        print(_section(f"孤儿 Artifact（已实现但无 REQ）{RED}[{len(result.orphan_artifacts)}]{RESET}"))
        by_kind: dict[str, list[CodeArtifact]] = {}
        for a in result.orphan_artifacts:
            by_kind.setdefault(a.kind, []).append(a)
        for kind, arts in sorted(by_kind.items()):
            print(f"\n  [{kind}]")
            for a in arts:
                print(f"    {YELLOW}?{RESET} {a.name:<45}  {a.file}:{a.line}")
        issues += len(result.orphan_artifacts)
    else:
        print(f"\n  {GREEN}✓{RESET} 所有已实现 artifact 均有对应 REQ")

    # ── Ghost REQs (REQ → Code 缺口) ─────────────────────────────────────
    if result.ghost_reqs:
        print(_section(f"幽灵 REQ（done/in_progress 但无对应 artifact）{YELLOW}[{len(result.ghost_reqs)}]{RESET}"))
        for req in result.ghost_reqs:
            print(f"  {YELLOW}?{RESET} {req.req_id:<10} [{req.status}]  {req.title}")
            if verbose:
                print(f"           acceptance: {req.acceptance}")
    else:
        print(f"  {GREEN}✓{RESET} 所有 done/in_progress REQ 均有对应 artifact")

    # ── Verbose: full match table ─────────────────────────────────────────
    if verbose:
        print(_section("Artifact → REQ 匹配明细"))
        for a in result.artifacts:
            status = f"{GREEN}{a.matched_req}{RESET}" if a.matched_req else f"{RED}UNMATCHED{RESET}"
            print(f"  {a.kind:<12} {a.name:<45}  → {status}")

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    if issues == 0:
        print(f"{GREEN}{BOLD}✓ 全部通过，需求与代码双向覆盖完整{RESET}")
    else:
        print(f"{RED}{BOLD}✗ 发现 {issues} 处缺口，见上方报告{RESET}")
    print()

    return 1 if issues > 0 else 0


# ─── 入口 ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="REQ coverage scanner")
    parser.add_argument("--verbose", action="store_true", help="显示完整匹配明细")
    parser.add_argument("--strict", action="store_true", help="有缺口时 exit(1)，用于 CI")
    args = parser.parse_args()

    result = ScanResult()
    load_reqs(result)
    extract_artifacts(result)
    match_artifacts_to_reqs(result)

    exit_code = print_report(result, verbose=args.verbose)

    if args.strict:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
