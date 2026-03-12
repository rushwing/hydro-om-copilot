---
harness_id: CLI-PB-001
component: agent operations / CLI invocation
owner: Engineering
version: 0.1
status: active
last_reviewed: 2026-03-12
---

# Harness Playbook — Agent CLI 调用模板

> 本文件收录 Claude Code 与 OpenAI Codex CLI 的常用调用模板。
> 适用场景：人工触发 Agent 任务、调试 harness 流程、临时补跑单步阶段。
> 自动化触发（GitHub Action）见 ci-standard.md §Git-Native Agent Loop。

---

## Claude Code (`claude`)

### 基础用法

```bash
# 交互式（默认）
claude

# 非交互式，单次任务
claude -p "prompt"

# 指定工作目录
claude --cwd /path/to/repo -p "prompt"
```

### 模板 A · 启动新会话（按 SOUL 标准流程）

```bash
claude -p "
Read agents/claude-code/SOUL.md, then harness/harness-index.md, then agents/claude-code/MEMORY.md.
Scan tasks/features/ for claimable tasks (status=test_designed, owner=unassigned).
Report what you find — do not claim anything yet.
"
```

### 模板 B · 认领并实现指定需求

```bash
claude -p "
Read agents/claude-code/SOUL.md.
Your task: implement REQ-<N>.
Follow Phase 1 (Claim PR) → Phase 2 (Implementation) → Phase 3 (PR) as defined in SOUL.md §SOP.
Read tasks/features/REQ-<N>.md and all test_case_ref TC files before writing any code.
Run bash scripts/local/test.sh before submitting the PR.
"
```

### 模板 C · Bug 修复

```bash
claude -p "
Read agents/claude-code/SOUL.md and harness/bug-standard.md.

IMPORTANT — use Claim PR mutex first (same pattern as REQ implementation):
1. Claim PR FIRST: branch claim/BUG-<N>, single-file commit (status=in_progress, owner=claude_code),
   push, open PR titled 'claim: BUG-<N>', enable auto-merge, wait for merge.
   If merge fails (conflict) → another agent claimed it, stop.
2. Only after claim merges: branch fix/BUG-<N>-<short-desc>
3. Read tasks/bugs/BUG-<N>.md fully — reproduction steps, related_req, related_tc
4. Fix the bug + add regression test
5. In the same commit (or final commit before PR): set status=fixed, fill 根因分析/修复方案 in BUG-<N>.md
   (per bug-standard.md §6.3: status=fixed transition must be inside the PR, not after)
6. bash scripts/local/test.sh must pass before opening PR
7. Open PR
"
```

### 模板 D · 本地质量检查（pre-PR）

```bash
claude -p "
Run all pre-commit checks defined in harness/ci-standard.md §Pre-commit:
  uv tool run ruff check backend/
  uv tool run ruff format --check backend/
  cd frontend && npm run type-check
  cd frontend && npm run lint
Report any failures. Fix lint/format issues automatically. Do not fix type errors without asking.
"
```

---

## OpenAI Codex (`codex`)

### 基础用法

```bash
# 交互式
codex

# 非交互式，全自动（workspace-write sandbox）
codex exec --full-auto "prompt"

# 需要网络访问时（如 gh pr review 需要连 GitHub API）
codex exec --dangerously-bypass-approvals-and-sandbox "prompt"
```

> **推荐直接使用 `scripts/harness.sh`**，它会自动选择正确的 sandbox 模式和预注入上下文。
> 下列模板供理解原理或手动调试使用。

### 模板 E · TC 设计（Acceptance Test Design）

```bash
codex exec --dangerously-bypass-approvals-and-sandbox "
Read agents/openai-codex/SOUL.md, harness/testing-standard.md, harness/requirement-standard.md.

Your task: design acceptance test cases for REQ-<N>.

IMPORTANT — claim mutex first, then do the work:
1. Claim PR FIRST: branch claim/REQ-<N>-tc, single-file commit (owner→openai_codex only),
   push, open PR titled 'claim: REQ-<N>-tc', enable auto-merge, wait for merge.
   If merge fails (conflict) → another agent claimed it, stop.
2. Only after claim succeeds: create branch test/REQ-<N>-tc-design
3. Read tasks/features/REQ-<N>.md fully
4. Create tasks/test-cases/TC-<N>-<desc>.md per testing-standard.md §TC 文档结构
5. Update tasks/features/REQ-<N>.md: add TC to test_case_ref, status=test_designed, owner=unassigned
6. Open PR for TC design (requires human review — do NOT auto-merge)
"
```

### 模板 F · PR Code Review

> 使用 `scripts/harness.sh review <PR号>` 代替手动调用，脚本会预注入 PR diff 和关联 REQ 内容。

```bash
# PR diff 和 REQ 内容由 harness.sh 预注入，无需 agent 自行探索
codex exec --dangerously-bypass-approvals-and-sandbox "
Read agents/openai-codex/SOUL.md, then harness/review-standard.md.

## Pre-fetched context for PR #<N>
[由 harness.sh 自动填充]

Check per review-standard.md. Post findings:
  gh pr review <N> --comment -b '...'         # non-blocking
  gh pr review <N> --request-changes -b '...' # blocking
Do NOT merge. HITL merge only.
"
```

### 模板 G · Bug 上报

```bash
codex exec --full-auto "
Read agents/openai-codex/SOUL.md and harness/bug-standard.md.
A potential bug was observed: <description of observed behavior>.

1. Determine if this is a genuine bug (vs design-as-intended)
2. If confirmed: create tasks/bugs/BUG-<next-id>.md following bug-standard.md §3.2 template
   - status: open (not confirmed yet — needs reproduction)
   - severity: assess per §4
   - Fill 现象描述, 预期行为, 复现步骤
3. Do not claim the fix — leave owner: unassigned
"
```

### 模板 H · 文档与代码一致性审查

```bash
codex exec --full-auto "
Read agents/openai-codex/SOUL.md.
Audit consistency between:
  - backend/app/agents/state.py (AgentState fields)
  - frontend/src/types/diagnosis.ts (TypeScript types)
  - docs/02-langgraph-architecture.md (architecture description)
Report any field mismatches, missing fields, or stale documentation.
Do not modify frozen files (list in CLAUDE.md §架构约束).
"
```

### 模板 I · Fix Review Comments（修复 PR review findings）

> 使用 `scripts/harness.sh fix-review <PR号>` 代替手动调用，脚本会预注入所有 review comments。

```bash
# review comments 由 harness.sh 预注入，无需 agent 自行探索
claude -p "
Read agents/claude-code/SOUL.md and harness/review-standard.md.

## Pre-fetched context for PR #<N>
[由 harness.sh 自动填充 — review 顶层 comments + inline comments]

## Your task
Address every finding in both sections:
1. Read the referenced file+line for each inline comment
2. Fix the code or doc (do NOT skip any finding)
3. If a finding is invalid, note why — do not silently ignore
4. After all fixes are pushed:
   a) Inline comments (have id) → reply via:
      gh api repos/{owner}/{repo}/pulls/<PR>/comments/<id>/replies -X POST -f body='Fixed in <sha>: <summary>'
   b) Top-level review summaries (no reply endpoint) → one general comment:
      gh pr review <PR> --comment -b 'Addressed review findings: ...'
Do NOT merge the PR — HITL merge only.
"
```

---

## 人工触发 Agent Loop（tasks/ 有新任务时）

```bash
# 查看当前可认领任务
./scripts/harness.sh status

# 手动触发 TC 设计（openai_codex）
./scripts/harness.sh tc-design REQ-<N>

# 手动触发实现（claude_code）
./scripts/harness.sh implement REQ-<N>

# Bug 修复 — 标准流程（独立 fix PR）
./scripts/harness.sh bugfix BUG-<N>

# Bug 修复 — Bundle（同一特性内，合入已有 REQ PR）
./scripts/harness.sh bugfix --bundle feat/REQ-<N>-xxx BUG-<N>

# Bug 修复 — Stacked PR（紧急，需先于依赖 PR 合并）
./scripts/harness.sh bugfix --stacked feat/REQ-<N>-xxx BUG-<N>

# 修复 PR review comments（claude_code）
./scripts/harness.sh fix-review <PR号>
```

---

## PR 依赖链处理（Dependent PRs）

当一个 PR 依赖另一个尚未 merge 的 PR 时，根据场景选择策略：

| 场景 | 策略 | 操作 |
|---|---|---|
| 实现 REQ 途中发现 bug（同属一个特性） | **Bundle** — 合并进同一 PR | 直接在 `feat/REQ-xxx` 分支修复，不开独立 PR |
| Bug 依赖某 REQ，但可等 HITL review 结束 | **Serialize** — `depends_on` 字段 | BUG-xxx.md frontmatter 写 `depends_on: [REQ-xxx]`，保持 `status: confirmed, owner: unassigned`；harness.sh 会自动跳过有依赖的 Bug |
| Bug 必须先于依赖 PR merge（紧急/reviewer 发现） | **Stacked PR** — PR base 指向依赖分支 | 见下方命令 |

### Stacked PR 操作流程

```bash
# 1. Claim PR mutex（先于任何修复工作）
git checkout main && git pull
git checkout -b claim/BUG-001
# 只改 tasks/bugs/BUG-001.md：status=in_progress, owner=claude_code
git add tasks/bugs/BUG-001.md
git commit -m "claim: BUG-001"
git push -u origin claim/BUG-001
gh pr create --title "claim: BUG-001" --body ""
gh pr merge --auto --squash
# 等待 claim PR 合并到 main；若冲突 → 另一 Agent 已认领，停止

# 2. claim 合并后，切 fix 分支（从依赖分支，不改动依赖分支本身）
git fetch origin
git checkout feat/REQ-001-xxx
git checkout -b fix/BUG-001-xxx
# 注意：fix 分支上 BUG-001.md 显示 confirmed（来自依赖分支），这是预期的

# 3. 开发并提交修复

# 4. 最终 commit 更新 BUG-001.md：status=fixed, owner=claude_code（从 confirmed/unassigned 推进）
#    retarget 到 main 时 HITL reviewer 解决 BUG-001.md 的一处冲突：
#      status: in_progress(main) vs fixed(fix) → 保留 fixed
#    owner 不冲突：两侧均为 claude_code，git 自动合并

# 5. PR base 设为依赖分支（不是 main）
gh pr create \
  --base feat/REQ-001-xxx \
  --title "fix: BUG-001 ..." \
  --body "depends on #<REQ-001-PR-number>"

# 6. REQ-001 PR merge 后：
#    - 若 REQ-001 分支被删除，GitHub 会自动将 BUG-001 PR 的 base 更新为 main
#    - 若分支未删除，需手动执行：gh pr edit <BUG-001-PR> --base main
# 7. BUG-001 PR 正常走 review → HITL merge
#    merge 时解决 BUG-001.md 的一处冲突：保留 status=fixed（owner 无冲突，见上方说明）
```

> Reviewer（openai_codex）review Stacked PR 时，只需看相对于 base branch 的增量 diff，
> 不对 base 部分内容提 blocking comment。见 review-standard.md §前置依赖检查。

---

## 注意事项

| 场景 | 建议模式 |
|---|---|
| TC 设计（Claim PR mutex 需要 git push + gh）| `codex exec --dangerously-bypass-approvals-and-sandbox` |
| Bug 上报（只写文件，无网络操作）| `codex exec --full-auto` |
| Bug 修复（harness bugfix）| `claude -p`（由 harness.sh 调用 Claude Code）|
| Review / 需要 gh 网络访问 | `codex exec --dangerously-bypass-approvals-and-sandbox` |
| Claude Code 非交互 | `claude -p "..."` |

> **永远不要在 Claim PR 以外的场景使用 `gh pr merge --auto`。**
> Implementation PR 必须人工 approve 后才能合并（见 ci-standard.md §HITL）。

---

## 变更日志

| 版本 | 日期 | 变更摘要 |
|---|---|---|
| 0.1 | 2026-03-12 | 初始版本；收录 A–H 八个常用模板，覆盖 TC 设计、实现认领、Bug 修复、PR Review、一致性审查 |
| 0.2 | 2026-03-13 | 修正 codex CLI 标志：`-a never -s danger-full-access` → `--dangerously-bypass-approvals-and-sandbox`；更新注意事项表格 |
| 0.3 | 2026-03-13 | 新增模板 I（Fix Review Comments）；fix-review 命令加入 harness.sh 和 Agent Loop 示例 |
