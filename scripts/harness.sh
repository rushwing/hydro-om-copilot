#!/usr/bin/env zsh
# harness.sh — Harness Engineering Agent 任务触发器
#
# 用法:
#   ./scripts/harness.sh review <PR号>          # Codex review 指定 PR
#   ./scripts/harness.sh implement <REQ-xxx>    # Claude Code 认领并实现需求
#   ./scripts/harness.sh tc-design <REQ-xxx>    # Codex 设计验收测试用例
#   ./scripts/harness.sh bugfix <BUG-xxx>       # Claude Code 认领并修复 Bug
#   ./scripts/harness.sh status                 # 打印当前可认领任务列表

# Extend PATH with known tool locations — avoids sourcing ~/.zshrc
# (sourcing brings in oh-my-zsh hooks that corrupt $() output)
for _d in \
  "/Applications/Codex.app/Contents/Resources" \
  "$HOME/.local/bin" \
  "$HOME/.npm-global/bin" \
  "$HOME/.npm/bin" \
  "/opt/homebrew/bin" \
  "/usr/local/bin" \
; do [[ -d "$_d" ]] && export PATH="$_d:$PATH"; done
unset _d

set -euo pipefail
trap 'echo "\n[harness] 错误：脚本在第 $LINENO 行退出" >&2' ERR

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLAUDE_APPROVAL="${CLAUDE_APPROVAL:-}"        # 留空则交互式
# review 需要调 gh（网络），必须用 danger-full-access 绕过 sandbox 网络限制
CODEX_REVIEW="codex exec -a never -s danger-full-access"
# 其他任务（tc-design 等）只需写文件，workspace-write 足够
CODEX_EXEC="codex exec --full-auto"

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

  # ── 预取 PR 上下文（避免 agent 自己探索，节省推理 token）────────────────────
  info "预取 PR #${pr} 上下文..."

  local pr_title pr_base pr_head pr_body pr_diff
  pr_title=$(gh pr view "$pr" --json title       --jq '.title')           || die "无法获取 PR #${pr}，请确认 PR 存在且 gh 已登录"
  pr_base=$( gh pr view "$pr" --json baseRefName --jq '.baseRefName')
  pr_head=$( gh pr view "$pr" --json headRefName --jq '.headRefName')
  pr_body=$( gh pr view "$pr" --json body        --jq '.body // ""')
  pr_diff=$( gh pr diff "$pr" 2>/dev/null || echo "(diff unavailable)")

  # ── 查找关联 REQ/BUG 并内联内容 ─────────────────────────────────────────────
  local task_id task_section=""
  task_id=$(echo "$pr_title $pr_body" | grep -oE '(REQ|BUG)-[0-9]+' | head -1)
  if [[ -n "$task_id" ]]; then
    local task_file=""
    [[ "$task_id" == REQ-* && -f "${REPO_ROOT}/tasks/features/${task_id}.md" ]] \
      && task_file="${REPO_ROOT}/tasks/features/${task_id}.md"
    [[ "$task_id" == BUG-* && -f "${REPO_ROOT}/tasks/bugs/${task_id}.md" ]] \
      && task_file="${REPO_ROOT}/tasks/bugs/${task_id}.md"
    if [[ -n "$task_file" ]]; then
      task_section="### Associated task: ${task_id}
$(cat "$task_file")
"
      info "已内联 ${task_id} → $(basename "$task_file")"
    else
      warn "${task_id} 在 PR 描述中提及，但 tasks/ 中未找到对应文件"
    fi
  fi

  # ── Stacked PR 提示 ──────────────────────────────────────────────────────────
  local stacked_note=""
  [[ "$pr_base" != "main" ]] && stacked_note="
> STACKED PR: base is \`${pr_base}\` (not main). Only review the incremental diff
> vs the base branch. Do NOT flag issues that belong to the base branch.
"

  # ── 触发 Codex（context 已预注入，无需 agent 自行探索）────────────────────────
  info "触发 Codex review PR #${pr} (base: ${pr_base} ← ${pr_head})..."
  local tmp_out session_log="${REPO_ROOT}/.harness_sessions"
  tmp_out=$(mktemp)

  $CODEX_REVIEW "Read agents/openai-codex/SOUL.md and harness/review-standard.md.

## Pre-fetched context for PR #${pr} — use directly, do NOT re-fetch

### Metadata
- Title: ${pr_title}
- Base → Head: ${pr_base} → ${pr_head}
${stacked_note}
### PR description
${pr_body}

${task_section}### Diff
\`\`\`diff
${pr_diff}
\`\`\`

## Your task
Check per review-standard.md: 前置依赖检查, 契约一致性, 安全性, 测试质量, 代码可读性.
${task_section:+Verify implementation against the Acceptance Criteria in the task file above.}
Post findings to GitHub (network is available):
  gh pr review ${pr} --comment -b '...'         # non-blocking
  gh pr review ${pr} --request-changes -b '...' # blocking

Do NOT merge. HITL merge only." 2>&1 | tee "$tmp_out"

  # ── Session ID 记录 ──────────────────────────────────────────────────────────
  local session_id
  session_id=$(grep 'session id:' "$tmp_out" | awk '{print $NF}' | head -1)
  if [[ -n "$session_id" ]]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)  review    pr=${pr}  ${session_id}" >> "$session_log"
    ok "Session → .harness_sessions  (resume only if interrupted: codex resume ${session_id})"
  fi
  rm -f "$tmp_out"
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
  local tmp_out session_log="${REPO_ROOT}/.harness_sessions"
  tmp_out=$(mktemp)
  local claude_cmd="claude -p"
  [[ -n "$CLAUDE_APPROVAL" ]] && claude_cmd="claude $CLAUDE_APPROVAL -p"
  $claude_cmd "
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
" 2>&1 | tee "$tmp_out"
  local session_id
  session_id=$(grep -E 'session[- ]id[: ]+' "$tmp_out" | grep -oE '[0-9a-f-]{36}' | head -1)
  [[ -n "$session_id" ]] && \
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)  implement  ${req}  ${session_id}" >> "$session_log" && \
    ok "Session → .harness_sessions"
  rm -f "$tmp_out"
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
  local tmp_out session_log="${REPO_ROOT}/.harness_sessions"
  tmp_out=$(mktemp)
  $CODEX_EXEC "
Read agents/openai-codex/SOUL.md, harness/testing-standard.md, harness/requirement-standard.md.

Your task: design acceptance test cases for ${req}.

IMPORTANT — follow this exact order (mutex first, then work):
1. Claim PR FIRST: branch claim/${req}-tc, single-file commit (owner→openai_codex only),
   push, open PR titled 'claim: ${req}-tc', enable auto-merge, wait for merge.
   If merge fails (conflict) → another agent claimed it, stop.
2. Only after claim succeeds: create implementation branch test/${req}-tc-design
3. Read tasks/features/${req}.md fully
4. Create tasks/test-cases/TC-${req#REQ-}-<desc>.md per testing-standard.md §TC 文档结构
   - Cover happy path, edge cases, error cases from Acceptance Criteria
   - Specify layer (L1 unit / L2 integration / L3 E2E)
5. Update tasks/features/${req}.md: add TC to test_case_ref, status=test_designed, owner=unassigned
6. Open PR for the TC design work (requires human review — do NOT auto-merge)
" 2>&1 | tee "$tmp_out"
  local session_id
  session_id=$(grep -E 'session[- ]id[: ]+' "$tmp_out" | grep -oE '[0-9a-f-]{36}' | head -1)
  [[ -n "$session_id" ]] && \
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)  tc-design  ${req}  ${session_id}" >> "$session_log" && \
    ok "Session → .harness_sessions"
  rm -f "$tmp_out"
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
  local tmp_out session_log="${REPO_ROOT}/.harness_sessions"
  tmp_out=$(mktemp)
  local claude_cmd="claude -p"
  [[ -n "$CLAUDE_APPROVAL" ]] && claude_cmd="claude $CLAUDE_APPROVAL -p"
  $claude_cmd "
Read agents/claude-code/SOUL.md and harness/bug-standard.md.

Your task: fix ${bug}.
1. Read tasks/bugs/${bug}.md — reproduction steps, related_req, related_tc
2. Branch: fix/${bug}-<short-desc>
3. First commit: claim only — status=in_progress, owner=claude_code in ${bug}.md (message: 'claim: ${bug}')
4. Fix the bug
5. Add regression test (required per bug-standard.md §7)
6. Fill in 根因分析 and 修复方案 in ${bug}.md, set status=fixed
7. bash scripts/local/test.sh must pass before opening PR
" 2>&1 | tee "$tmp_out"
  local session_id
  session_id=$(grep -E 'session[- ]id[: ]+' "$tmp_out" | grep -oE '[0-9a-f-]{36}' | head -1)
  [[ -n "$session_id" ]] && \
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ)  bugfix     ${bug}  ${session_id}" >> "$session_log" && \
    ok "Session → .harness_sessions"
  rm -f "$tmp_out"
}

cmd_status() {
  info "扫描可认领任务...\n"

  local features_dir="${REPO_ROOT}/tasks/features"
  local bugs_dir="${REPO_ROOT}/tasks/bugs"

  echo -e "${CYAN}── 可 TC 设计（status=ready, owner=unassigned）──${NC}"
  if [[ -d "$features_dir" ]]; then
    local found=0
    for f in "$features_dir"/*.md(N); do
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
    for f in "$features_dir"/*.md(N); do
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
    for f in "$bugs_dir"/*.md(N); do
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
