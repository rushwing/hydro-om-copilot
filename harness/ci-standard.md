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
        # 扫描 tasks/features/：status=test_designed, owner=unassigned
        # 输出下一个可认领任务，供人工决定是否触发 Agent
```

> `scripts/agent-loop.py` 当前为 stub（仅打印可认领任务列表）。
> 实际 Agent 调用（`claude -p`）在人工确认后手动触发，直到流程稳定。

---

## 待补充

- [ ] GitHub Actions workflow 文件（`.github/workflows/`）
- [ ] Pre-commit hook 安装脚本（`scripts/install-hooks.sh`）
- [ ] `scripts/agent-loop.py` 完整实现
- [ ] 测试失败时的处理流程与通知机制
- [ ] Canary 预算监控接入

---

## 变更日志

| 版本 | 日期 | 变更摘要 |
|---|---|---|
| 0.1 | 2026-03-12 | 初始 stub；记录 pre-commit 命令、PR gate 状态和 Agent Loop 设计草稿 |
