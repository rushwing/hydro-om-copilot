---
harness_id: CI-STD-001
component: CI / quality gates / automation
owner: Engineering
version: 0.1
status: stub
last_reviewed: 2026-03-12
---

# Harness Standard — CI 与质量门禁规程 [STUB]

> **当前状态：stub。** 记录已知的 pre-commit 要求和 PR gate 原则。
> GitHub Actions workflow 和 pre-commit hook 安装脚本待补充。

---

## Claim PR 配置（已确定）

认领互斥锁依赖 GitHub auto-merge 与 git 冲突检测，需要以下 repo 配置：

| 配置项 | 设置值 | 说明 |
|---|---|---|
| Allow auto-merge | ✅ 启用 | Settings → General → Allow auto-merge |
| Claim PR required reviews | 0 | 标题匹配 `^claim:` 的 PR 无需 human review |
| Implementation PR required reviews | 1 | HITL 强制要求 |
| Branch protection: require linear history | 推荐 | 防止并发 merge 造成无声覆盖 |

> **当前状态**：auto-merge 未在 repo 配置，Claim PR 机制尚未完全生效。
> 在正式接入 Agent 自动化之前，人工 pre-allocation 仍是主要防冲突手段。

---

## 已确定原则

### Pre-commit 检查（本地，开发者 / Agent 必跑）

```bash
# 后端
uv tool run ruff check backend/          # lint
uv tool run ruff format --check backend/ # format check

# 前端
cd frontend && npm run type-check        # tsc --noEmit
cd frontend && npm run lint              # eslint
```

### PR Gate（合并前必须通过）

| 检查项 | 工具 | 当前状态 |
|---|---|---|
| 后端 lint | ruff | 手动运行 |
| 后端 format | ruff format | 手动运行 |
| 前端 type-check | tsc | 手动运行 |
| 前端 lint | eslint | 手动运行 |
| 后端单元测试 | pytest | 🔲 CI 未接入 |
| 前端单元测试 | vitest | 🔲 未安装 |
| E2E smoke | playwright | 🔲 未安装 |
| 真实 LLM canary | pytest -m canary | 🔲 仅 nightly/手动 |

### 测试环境变量（CI 必须设置）

```bash
AUTO_RANDOM_PROBLEMS_GEN=false    # 禁止后台轮询
SENSOR_POLL_INTERVAL=999
ANTHROPIC_API_KEY=mock            # 非 canary 环境
```

---

## Git-Native Agent Loop（设计草稿）

当前规划的触发机制：

```yaml
# .github/workflows/agent-loop.yml（待实现）
on:
  pull_request:
    types: [closed]
    branches: [main]

jobs:
  find-next-task:
    if: github.event.pull_request.merged == true
    steps:
      - uses: actions/checkout@v4
      - name: Find next claimable task
        run: python scripts/agent-loop.py
        # Pass 1：扫描 tasks/features/：status=ready, owner=unassigned, test_case_ref=[]
        #         → 触发 openai_codex TC 设计（harness.sh tc-design）
        # Pass 2：扫描 tasks/features/：status=test_designed, owner=unassigned
        #         → 触发 claude_code 实现（harness.sh implement）
        # 输出可认领任务列表，供人工决定是否触发 Agent
```

> `scripts/agent-loop.py` 已实现（扫描并打印两类可认领任务列表）。
> 实际 Agent 调用通过 `harness.sh tc-design / implement` 在人工确认后手动触发，直到 GitHub Action workflow 接入。

---

## 待补充

- [ ] GitHub Actions workflow 文件（`.github/workflows/`）
- [ ] Pre-commit hook 安装脚本（`scripts/install-hooks.sh`）
- [ ] 测试失败时的处理流程与通知机制
- [ ] Canary 预算监控接入

---

## 变更日志

| 版本 | 日期 | 变更摘要 |
|---|---|---|
| 0.1 | 2026-03-12 | 初始 stub；记录 pre-commit 命令、PR gate 状态和 Agent Loop 设计草稿 |
