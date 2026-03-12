#!/usr/bin/env bash
# harness.sh — Harness Engineering Agent 任务触发器
#
# 用法:
#   ./scripts/harness.sh review <PR号>          # Codex review 指定 PR
#   ./scripts/harness.sh implement <REQ-xxx>    # Claude Code 认领并实现需求
#   ./scripts/harness.sh tc-design <REQ-xxx>    # Codex 设计验收测试用例
#   ./scripts/harness.sh bugfix <BUG-xxx>       # Claude Code 认领并修复 Bug
#   ./scripts/harness.sh status                 # 打印当前可认领任务列表

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLAUDE_APPROVAL="${CLAUDE_APPROVAL:-}"        # 留空则交互式
CODEX_APPROVAL="${CODEX_APPROVAL:---approval-mode full-auto}"

# ── 颜色 ──────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[harness]${NC} $*"; }
ok()    { echo -e "${GREEN}[harness]${NC} $*"; }
warn()  { echo -e "${YELLOW}[harness]${NC} $*"; }
die()   { echo -e "${RED}[harness]${NC} $*" >&2; exit 1; }

# ── 工具检查 ──────────────────────────────────────────────────────────────────
require() {
  command -v "$1" &>/dev/null || die "'$1' not found. $2"
}

# ── 子命令 ────────────────────────────────────────────────────────────────────

cmd_review() {
  local pr="${1:-}"
  [[ -n "$pr" ]] || die "Usage: harness review <PR号>\n  例：harness review 18"
  require codex "Install: npm install -g @openai/codex"
  require gh    "Install: https://cli.github.com"

  # 验证 PR 存在
  gh pr view "$pr" --json number,title,state -q '"PR #\(.number): \(.title) [\(.state)]"' \
    || die "PR #$pr 不存在或无权访问"

  info "触发 Codex review PR #${pr} ..."
  codex $CODEX_APPROVAL "
Read agents/openai-codex/SOUL.md, then harness/review-standard.md.

Your task: review PR #${pr}.
1. gh pr view ${pr} --json number,title,body,baseRefName,headRefName
2. gh pr diff ${pr}
3. If base branch is not main, this is a Stacked PR — only review the incremental diff vs the base branch per review-standard.md §前置依赖检查
4. Find associated REQ or BUG in tasks/ (PR title or body should mention it)
5. If found, read that file — focus on Acceptance Criteria
6. Check per review-standard.md: 契约一致性, 安全性, 测试质量, 代码可读性
7. Post findings:
   - Non-blocking: gh pr review ${pr} --comment -b '...'
   - Blocking:     gh pr review ${pr} --request-changes -b '...'

Do NOT merge. HITL merge only.
"
}

cmd_implement() {
  local req="${1:-}"
  [[ -n "$req" ]] || die "Usage: harness implement <REQ-xxx>\n  例：harness implement REQ-001"
  require claude "Install: https://claude.ai/code"

  local req_file="${REPO_ROOT}/tasks/features/${req}.md"
  [[ -f "$req_file" ]] || die "${req_file} 不存在"

  # 检查状态
  local status owner
  status=$(grep '^status:' "$req_file" | awk '{print $2}' | tr -d '"')
  owner=$(grep '^owner:'  "$req_file" | awk '{print $2}' | tr -d '"')

  [[ "$status" == "test_designed" ]] \
    || warn "${req} status=${status}，期望 test_designed。确认后继续..."
  [[ "$owner" == "unassigned" ]] \
    || die "${req} 已被 ${owner} 认领，无法重复认领"

  info "触发 Claude Code 认领并实现 ${req} ..."
  local prompt
  if [[ -n "$CLAUDE_APPROVAL" ]]; then
    claude $CLAUDE_APPROVAL -p "
Read agents/claude-code/SOUL.md.

Your task: implement ${req}.
Follow SOUL.md §SOP Phase 1 (Claim PR) then Phase 2 (Implementation) then Phase 3 (PR).
1. Claim PR: branch claim/${req}, single-file commit, auto-merge PR, verify merged
2. Implementation branch: feat/${req}-<short-desc>
3. Read tasks/features/${req}.md fully — Acceptance Criteria and In Scope
4. Read all TC files in test_case_ref before writing any code
5. Write tests first, then implementation
6. bash scripts/local/test.sh must pass before opening PR
7. Set ${req}.md status=review and open PR (Draft until tests pass)
"
  else
    claude -p "
Read agents/claude-code/SOUL.md.

Your task: implement ${req}.
Follow SOUL.md §SOP Phase 1 (Claim PR) then Phase 2 (Implementation) then Phase 3 (PR).
1. Claim PR: branch claim/${req}, single-file commit, auto-merge PR, verify merged
2. Implementation branch: feat/${req}-<short-desc>
3. Read tasks/features/${req}.md fully — Acceptance Criteria and In Scope
4. Read all TC files in test_case_ref before writing any code
5. Write tests first, then implementation
6. bash scripts/local/test.sh must pass before opening PR
7. Set ${req}.md status=review and open PR (Draft until tests pass)
"
  fi
}

cmd_tc_design() {
  local req="${1:-}"
  [[ -n "$req" ]] || die "Usage: harness tc-design <REQ-xxx>\n  例：harness tc-design REQ-001"
  require codex "Install: npm install -g @openai/codex"

  local req_file="${REPO_ROOT}/tasks/features/${req}.md"
  [[ -f "$req_file" ]] || die "${req_file} 不存在"

  local status owner
  status=$(grep '^status:' "$req_file" | awk '{print $2}' | tr -d '"')
  owner=$(grep '^owner:'  "$req_file" | awk '{print $2}' | tr -d '"')

  [[ "$status" == "ready" ]] \
    || warn "${req} status=${status}，期望 ready。确认后继续..."
  [[ "$owner" == "unassigned" ]] \
    || die "${req} 已被 ${owner} 认领"

  info "触发 Codex TC 设计 ${req} ..."
  codex $CODEX_APPROVAL "
Read agents/openai-codex/SOUL.md, harness/testing-standard.md, harness/requirement-standard.md.

Your task: design acceptance test cases for ${req}.
1. Read tasks/features/${req}.md fully
2. Create tasks/test-cases/TC-${req#REQ-}-<desc>.md following testing-standard.md §TC 文档结构
   - Cover happy path, edge cases, error cases from Acceptance Criteria
   - Specify layer (L1 unit / L2 integration / L3 E2E) per testing-standard.md §分层策略
3. After TC file is created:
   - Update tasks/features/${req}.md: add TC to test_case_ref, status=test_designed, owner=unassigned
   - Use Claim PR mutex (branch claim/${req}-tc) per requirement-standard.md §8.2 Mode A
"
}

cmd_bugfix() {
  local bug="${1:-}"
  [[ -n "$bug" ]] || die "Usage: harness bugfix <BUG-xxx>\n  例：harness bugfix BUG-001"
  require claude "Install: https://claude.ai/code"

  local bug_file="${REPO_ROOT}/tasks/bugs/${bug}.md"
  [[ -f "$bug_file" ]] || die "${bug_file} 不存在"

  local status owner
  status=$(grep '^status:' "$bug_file" | awk '{print $2}' | tr -d '"')
  owner=$(grep '^owner:'  "$bug_file" | awk '{print $2}' | tr -d '"')

  [[ "$status" == "confirmed" ]] \
    || warn "${bug} status=${status}，期望 confirmed。确认后继续..."
  [[ "$owner" == "unassigned" ]] \
    || die "${bug} 已被 ${owner} 认领"

  info "触发 Claude Code 认领并修复 ${bug} ..."
  local prompt="
Read agents/claude-code/SOUL.md and harness/bug-standard.md.

Your task: fix ${bug}.
1. Read tasks/bugs/${bug}.md — reproduction steps, related_req, related_tc
2. Branch: fix/${bug}-<short-desc>
3. First commit: claim only — status=in_progress, owner=claude_code in ${bug}.md (message: 'claim: ${bug}')
4. Fix the bug
5. Add regression test (required per bug-standard.md §7)
6. Fill in 根因分析 and 修复方案 in ${bug}.md, set status=fixed
7. bash scripts/local/test.sh must pass before opening PR
"
  if [[ -n "$CLAUDE_APPROVAL" ]]; then
    claude $CLAUDE_APPROVAL -p "$prompt"
  else
    claude -p "$prompt"
  fi
}

cmd_status() {
  info "扫描可认领任务...\n"

  local features_dir="${REPO_ROOT}/tasks/features"
  local bugs_dir="${REPO_ROOT}/tasks/bugs"

  echo -e "${CYAN}── 可 TC 设计（status=ready, owner=unassigned）──${NC}"
  if [[ -d "$features_dir" ]]; then
    local found=0
    for f in "$features_dir"/*.md; do
      [[ -f "$f" ]] || continue
      local s o
      s=$(grep '^status:' "$f" 2>/dev/null | awk '{print $2}' | tr -d '"')
      o=$(grep '^owner:'  "$f" 2>/dev/null | awk '{print $2}' | tr -d '"')
      id=$(grep '^req_id:' "$f" 2>/dev/null | awk '{print $2}' | tr -d '"')
      title=$(grep '^title:' "$f" 2>/dev/null | sed 's/^title: *//')
      if [[ "$s" == "ready" && "$o" == "unassigned" ]]; then
        echo -e "  ${GREEN}●${NC} ${id}  ${title}"
        found=1
      fi
    done
    [[ $found -eq 1 ]] || echo "  (无)"
  else
    echo "  (tasks/features/ 目录不存在)"
  fi

  echo ""
  echo -e "${CYAN}── 可实现（status=test_designed, owner=unassigned）──${NC}"
  if [[ -d "$features_dir" ]]; then
    local found=0
    for f in "$features_dir"/*.md; do
      [[ -f "$f" ]] || continue
      local s o
      s=$(grep '^status:' "$f" 2>/dev/null | awk '{print $2}' | tr -d '"')
      o=$(grep '^owner:'  "$f" 2>/dev/null | awk '{print $2}' | tr -d '"')
      id=$(grep '^req_id:' "$f" 2>/dev/null | awk '{print $2}' | tr -d '"')
      title=$(grep '^title:' "$f" 2>/dev/null | sed 's/^title: *//')
      if [[ "$s" == "test_designed" && "$o" == "unassigned" ]]; then
        echo -e "  ${GREEN}●${NC} ${id}  ${title}"
        found=1
      fi
    done
    [[ $found -eq 1 ]] || echo "  (无)"
  else
    echo "  (tasks/features/ 目录不存在)"
  fi

  echo ""
  echo -e "${CYAN}── 可修复 Bug（status=confirmed, owner=unassigned）──${NC}"
  if [[ -d "$bugs_dir" ]]; then
    local found=0
    for f in "$bugs_dir"/*.md; do
      [[ -f "$f" ]] || continue
      local s o
      s=$(grep '^status:' "$f" 2>/dev/null | awk '{print $2}' | tr -d '"')
      o=$(grep '^owner:'  "$f" 2>/dev/null | awk '{print $2}' | tr -d '"')
      id=$(grep '^bug_id:' "$f" 2>/dev/null | awk '{print $2}' | tr -d '"')
      title=$(grep '^title:' "$f" 2>/dev/null | sed 's/^title: *//')
      sev=$(grep '^severity:' "$f" 2>/dev/null | awk '{print $2}' | tr -d '"')
      if [[ "$s" == "confirmed" && "$o" == "unassigned" ]]; then
        echo -e "  ${GREEN}●${NC} ${id} [${sev}]  ${title}"
        found=1
      fi
    done
    [[ $found -eq 1 ]] || echo "  (无)"
  else
    echo "  (tasks/bugs/ 目录不存在)"
  fi

  echo ""
}

# ── 入口 ──────────────────────────────────────────────────────────────────────
usage() {
  cat <<EOF
用法: harness <command> [args]

Commands:
  review <PR号>        触发 Codex review 指定 PR
  implement <REQ-xxx>  触发 Claude Code 认领并实现需求
  tc-design <REQ-xxx>  触发 Codex 设计验收测试用例
  bugfix <BUG-xxx>     触发 Claude Code 认领并修复 Bug
  status               列出当前所有可认领任务

环境变量:
  CODEX_APPROVAL   codex --approval-mode 值（默认 full-auto）
  CLAUDE_APPROVAL  claude 的 approval flag（默认空，即交互式）

示例:
  ./scripts/harness.sh review 18
  ./scripts/harness.sh implement REQ-001
  ./scripts/harness.sh tc-design REQ-002
  ./scripts/harness.sh bugfix BUG-001
  ./scripts/harness.sh status
EOF
}

cd "$REPO_ROOT"

case "${1:-}" in
  review)     cmd_review    "${2:-}" ;;
  implement)  cmd_implement "${2:-}" ;;
  tc-design)  cmd_tc_design "${2:-}" ;;
  bugfix)     cmd_bugfix    "${2:-}" ;;
  status)     cmd_status ;;
  -h|--help|help|"") usage ;;
  *) die "未知命令: $1\n$(usage)" ;;
esac
