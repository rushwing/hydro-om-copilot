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
Fix BUG-<N>: read tasks/bugs/BUG-<N>.md for reproduction steps and root cause hints.
Branch: fix/BUG-<N>-<short-desc>. First commit: claim only (status=in_progress, owner=claude_code).
PR must include: fix code + regression test + filled 根因分析/修复方案 in BUG-<N>.md.
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

# 非交互式，全自动（适合 CI/无人值守）
codex --approval-mode full-auto "prompt"

# 半自动（写文件前确认，适合人工监督）
codex --approval-mode auto-edit "prompt"
```

### 模板 E · TC 设计（Acceptance Test Design）

```bash
codex --approval-mode auto-edit "
Read agents/openai-codex/SOUL.md, harness/testing-standard.md, and harness/requirement-standard.md.
Design acceptance test cases for REQ-<N>: read tasks/features/REQ-<N>.md fully.
Create tasks/test-cases/TC-<N>-<desc>.md following testing-standard.md §TC 文档结构.
After creating the TC file:
  1. Update tasks/features/REQ-<N>.md: add TC-<N> to test_case_ref, set status=test_designed, owner=unassigned
  2. Use the Claim PR mutex (claim/REQ-<N>-tc branch) as defined in requirement-standard.md §8.2 Mode A
"
```

### 模板 F · PR Code Review

```bash
codex --approval-mode full-auto "
Read agents/openai-codex/SOUL.md, then harness/review-standard.md.

Review PR #<N>:
1. gh pr diff <N>          — see all changes
2. gh pr view <N>          — get title, description, linked REQ
3. Read tasks/features/REQ-<N>.md — focus on Acceptance Criteria
4. Check against review-standard.md: 契约一致性, 安全性, 测试质量, 代码可读性

Post findings:
  gh pr review <N> --comment -b '...'         # non-blocking notes
  gh pr review <N> --request-changes -b '...' # blocking issues

Do NOT merge. HITL merge only.
"
```

### 模板 G · Bug 上报

```bash
codex --approval-mode auto-edit "
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
codex --approval-mode full-auto "
Read agents/openai-codex/SOUL.md.
Audit consistency between:
  - backend/app/agents/state.py (AgentState fields)
  - frontend/src/types/diagnosis.ts (TypeScript types)
  - docs/02-langgraph-architecture.md (architecture description)
Report any field mismatches, missing fields, or stale documentation.
Do not modify frozen files (list in CLAUDE.md §架构约束).
"
```

---

## 人工触发 Agent Loop（tasks/ 有新任务时）

```bash
# 查看当前可认领任务
python scripts/agent-loop.py   # stub：仅打印列表

# 手动触发 TC 设计（openai_codex）
codex --approval-mode auto-edit "$(cat harness/agent-cli-playbook.md | grep -A 20 '模板 E')"

# 手动触发实现（claude_code）
claude -p "$(cat harness/agent-cli-playbook.md | grep -A 15 '模板 B')"
```

---

## PR 依赖链处理（Dependent PRs）

当一个 PR 依赖另一个尚未 merge 的 PR 时，根据场景选择策略：

| 场景 | 策略 | 操作 |
|---|---|---|
| 实现 REQ 途中发现 bug（同属一个特性） | **Bundle** — 合并进同一 PR | 直接在 `feat/REQ-xxx` 分支修复，不开独立 PR |
| Bug 依赖某 REQ，但可等 HITL review 结束 | **Serialize** — 任务级 `depends_on` | BUG-xxx.md 中写 `depends_on: [REQ-xxx]`，等 REQ done 后再认领 |
| Bug 必须先于依赖 PR merge（紧急/reviewer 发现） | **Stacked PR** — PR base 指向依赖分支 | 见下方命令 |

### Stacked PR 操作流程

```bash
# 1. 在依赖 PR 的分支上开发
git checkout feat/REQ-001-xxx
git checkout -b fix/BUG-001-xxx

# 2. 开发并提交修复

# 3. PR base 设为依赖分支（不是 main）
gh pr create \
  --base feat/REQ-001-xxx \
  --title "fix: BUG-001 ..." \
  --body "depends on #<REQ-001-PR-number>"

# 4. REQ-001 PR merge 进 main 后，GitHub 自动更新 BUG-001 PR 的 base 为 main
# 5. BUG-001 PR 正常走 review → HITL merge
```

> Reviewer（openai_codex）review Stacked PR 时，只需看相对于 base branch 的增量 diff，
> 不对 base 部分内容提 blocking comment。见 review-standard.md §前置依赖检查。

---

## 注意事项

| 场景 | 建议模式 |
|---|---|
| 无人值守 CI / GitHub Action | `--approval-mode full-auto` |
| 人工监督，允许自动写文件 | `--approval-mode auto-edit` |
| 仅建议，人工确认每步 | `--approval-mode suggest`（codex 默认）|
| Claude Code 非交互 | `-p "..."` |

> **永远不要在 Claim PR 以外的场景使用 `gh pr merge --auto`。**
> Implementation PR 必须人工 approve 后才能合并（见 ci-standard.md §HITL）。

---

## 变更日志

| 版本 | 日期 | 变更摘要 |
|---|---|---|
| 0.1 | 2026-03-12 | 初始版本；收录 A–H 八个常用模板，覆盖 TC 设计、实现认领、Bug 修复、PR Review、一致性审查 |
