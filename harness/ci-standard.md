---
harness_id: CI-STD-001
component: CI / quality gates / automation
owner: Engineering
version: 0.4
status: active
last_reviewed: 2026-03-15
---

# Harness Standard — CI 与质量门禁规程

> **v0.3**：补充 REQ 覆盖率门禁（`check_req_coverage.py`）与 `draft → ready` 前置检查规程。
> GitHub Actions workflow 已实现（`.github/workflows/agent-loop.yml`，REQ-012 ✅）。

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
| 后端 lint | ruff | ✅ CI job: `backend-lint` |
| 后端 format | ruff format | ✅ CI job: `backend-lint` |
| 前端 type-check | tsc | ✅ CI job: `frontend-checks` |
| 前端 lint | eslint | ✅ CI job: `frontend-checks` |
| **REQ 覆盖率** | **check_req_coverage.py** | ✅ CI job: `req-coverage` |
| 后端单元测试 | pytest | ✅ CI job: `backend-tests` |
| 前端单元测试 | vitest | ✅ CI job: `frontend-checks` |
| E2E P0 smoke | playwright `--grep @P0` | ✅ CI job: `e2e-smoke`（`npm run e2e:p0`，REQ-026）|
| 真实 LLM canary | pytest -m canary | 🔲 仅 weekly/手动 |

### 测试环境变量（CI 必须设置）

```bash
AUTO_RANDOM_PROBLEMS_GEN=false    # 禁止后台轮询
SENSOR_POLL_INTERVAL=999
ANTHROPIC_API_KEY=mock            # 非 canary 环境
```

---

---

## REQ 覆盖率门禁

### 目的

防止"代码超前于需求"（实现已合并但无对应 REQ）和"需求字段不完整就流转状态"两类问题。

### 脚本

```bash
# 位置：scripts/check_req_coverage.py
python3 scripts/check_req_coverage.py          # 报告模式（人工查看）
python3 scripts/check_req_coverage.py --strict  # CI 模式（有缺口时 exit 1）
python3 scripts/check_req_coverage.py --verbose # 显示完整 artifact → REQ 匹配明细
```

### 检查内容

**Code → REQ（孤儿检测）**：已实现 artifact 必须有对应 REQ

| Artifact 类型 | 提取方式 |
|---|---|
| FastAPI 路由 | `@router.{method}("path")` |
| React 组件 | `export (function\|const) ComponentName` |
| LangGraph 节点 | `graph.add_node("name")` |
| MCP 工具函数 | `@mcp.tool` 装饰器 |

**REQ → Code（幽灵检测）**：`done`/`in_progress` 且无 `code_refs` 的 REQ 必须有 artifact 匹配

**Frontmatter 完整性**：所有 REQ 文档的 10 个字段合法（触发 `draft → ready` 的强制前置条件）

### 匹配优先级

```
code_refs 精确文件路径  >  字面子串匹配  >  路由路径分段  >  关键词 token 集合
```

有 `code_refs` 的 REQ 跳过关键词匹配，避免散文描述产生假阳性。有 `code_refs` 的 REQ 同时排除幽灵检测（Python 类/脚本不产生可扫描 artifact）。

### 何时运行

| 时机 | 命令 | 说明 |
|---|---|---|
| 将 REQ 从 `draft` 改为 `ready` 前 | `--strict` | frontmatter 检查，见 requirement-standard.md §6.4 |
| 提 PR 合并到 `main` 前 | `--strict` | 防止孤儿 artifact 进入主干 |
| 接入 CI 后（见 REQ-012）| `--strict` | 自动阻断不合规 PR |

### CI 配置（待实现，见 REQ-012）

```yaml
# .github/workflows/agent-loop.yml（片段）
- name: REQ coverage check
  run: python3 scripts/check_req_coverage.py --strict
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

---

## 定时构建（Daily / Weekly）

### 触发时间

| 构建类型 | cron | 描述 |
|----------|------|------|
| Daily | `0 2 * * *` | 每日 02:00 UTC，P0+P1 E2E |
| Weekly | `0 3 * * 0` | 每周日 03:00 UTC，全量 E2E + LLM canary |

### 运行内容

| 构建类型 | E2E 范围 | canary | 失败处理 |
|----------|----------|--------|---------|
| Daily | P0+P1（`npm run e2e:daily`）| 不跑 | 自动开 issue |
| Weekly | 全量（`npm run e2e`）| pytest -m canary | 自动开 issue |

### 自动开 issue 规格

- **触发条件**：job 以 `failure()` 结束
- **实现方式**：`actions/github-script@v7`（jobs 需声明 `permissions: issues: write`）
- **issue 标题格式**：`[CI] {Daily|Weekly} E2E {类型} failed — YYYY-MM-DD`
- **labels**：`bug`, `ci-failure`
- **issue 正文**：包含 Actions Run URL 和中文排查步骤
- **关闭时机**：人工确认根因后手动关闭

> **不定义 Release 规则**：发布流程待业务成熟后再制定，当前不设版本号门禁或 tag 触发。

### 并发控制

定时构建使用独立 concurrency group（`github.event.schedule` 值），不与 PR/push build 互相取消：

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.event_name == 'schedule' && github.event.schedule || github.ref }}
  cancel-in-progress: ${{ github.event_name != 'schedule' }}
```

---

## 待补充

- [x] GitHub Actions workflow 文件（`.github/workflows/agent-loop.yml`，REQ-012 已完成）
- [x] 定时构建（Daily / Weekly）及自动开 issue
- [ ] Pre-commit hook 安装脚本（`scripts/install-hooks.sh`）
- [ ] Canary 预算监控接入
- [ ] `check_req_coverage.py` 扩展：Python 类/函数提取器（覆盖 HybridRetriever、FaultAggregator 等）

---

## 变更日志

| 版本 | 日期 | 变更摘要 |
|---|---|---|
| 0.1 | 2026-03-12 | 初始 stub；记录 pre-commit 命令、PR gate 状态和 Agent Loop 设计草稿 |
| 0.2 | 2026-03-13 | 补充 REQ 覆盖率门禁规程（check_req_coverage.py）；将 frontmatter 检查绑定为 draft→ready 前置条件；更新 PR Gate 表格；status 升级为 active |
| 0.3 | 2026-03-14 | 落地 REQ-012：创建 `.github/workflows/agent-loop.yml`，5 个 job（backend-lint、backend-tests、frontend-checks、req-coverage、agent-loop）；PR Gate 全栏更新为 CI 已接入 |
| 0.4 | 2026-03-15 | 落地 REQ-026：新增 `e2e-smoke` CI job（Playwright，4 条 pending-archive 用例）；PR Gate E2E 行标注 ✅ CI job 已接入 |
| 0.5 | 2026-03-15 | 新增定时构建节（Daily P0+P1、Weekly 全量）；PR gate E2E 收窄为 P0 only（`e2e:p0`）；定义自动开 issue 规格；声明不设 Release 规则；新增并发控制说明；workflow 新增 `daily-e2e` / `weekly-e2e` jobs |
