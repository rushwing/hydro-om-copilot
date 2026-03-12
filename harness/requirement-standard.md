---
harness_id: REQ-STD-001
component: requirements / task routing
owner: Engineering
version: 0.1
status: draft
last_reviewed: 2026-03-12
---

# Harness Standard — 需求管理与多 Agent 任务认领规程

> 本规范定义 Hydro O&M Copilot 在 Harness Engineering 范式下的需求记录方式、
> 状态机、优先级、Phase 管理，以及多 Agent 自动认领与交接规则。
> 目标是让 Claude Code 与 OpenAI Codex 能在同一套 repo 内规范下读取需求、
> 判断可认领任务、执行开发，并把实现状态回写到统一位置。

---

## 1. 适用范围

- **组件**：需求文档、任务拆分、Agent 认领规则、状态回写规则
- **输入类型**：Phase 文档、需求项文档、阻塞说明、验收标准、认领信息
- **触发时机**：
  - [ ] 新增功能需求时
  - [ ] 拆分实现任务时
  - [ ] Agent 启动开发前
  - [ ] 任务状态变化时
  - [ ] PR 合并或需求关闭时

---

## 2. 设计原则

### 2.1 Repo 内需求是 Agent 可执行层的事实源

| 项目 | 内容 |
|---|---|
| 规则 | 与代码实现直接相关、需要 Agent 读取并执行的需求，必须记录在 repo 内 |
| 目的 | 让 Agent 在本地即可获得稳定上下文，不依赖聊天记录或外部项目管理工具 |
| 好示例 | 某个自动诊断 stop 语义、历史归档流转、测试补齐要求写入 `tasks/items/` |
| 坏示例 | 关键验收条件只存在于聊天里，repo 内无对应需求项 |

### 2.2 需求文档应短小、结构化、可认领

| 项目 | 内容 |
|---|---|
| 规则 | 每个需求项文档只描述一个可交付任务单元，必须包含明确验收标准 |
| 目的 | 降低 Agent 理解偏差，方便自动判断“是否可开始/是否完成” |
| 好示例 | “修复 SSE 断流时 session log 清理”单独成项，含验收条件 |
| 坏示例 | 一个文档同时混写 10 个目标、多个阶段和大量开放讨论 |

### 2.3 状态必须简单、可迁移

| 项目 | 内容 |
|---|---|
| 规则 | 只使用本规范定义的 6 个状态；禁止自行扩展近义状态 |
| 目的 | 避免多 Agent 协作时状态语义漂移 |
| 好示例 | `ready -> in_progress -> review -> done` |
| 坏示例 | `doing`、`wip`、`almost_done`、`ready-for-next-pass` 混用 |

---

## 3. 目录规范

### 3.1 目录结构

```text
tasks/                  # 所有待执行工作项的根目录
  phases/               # Phase 定义文档 (PHASE-xxx)
  features/             # 功能需求项 (REQ-xxx)
  bugs/                 # Bug 报告 (BUG-xxx，见 harness/bug-standard.md)
  test-cases/           # 测试用例设计 (TC-xxx，先于实现创建)
  archive/
    done/               # 已完成归档
    cancelled/          # 已废弃归档
```

### 3.2 目录职责

| 目录 | ID 前缀 | 职责 |
|---|---|---|
| `tasks/phases/` | `PHASE-xxx` | 记录阶段目标、范围、入口/退出条件 |
| `tasks/features/` | `REQ-xxx` | 当前活跃的功能需求项 |
| `tasks/bugs/` | `BUG-xxx` | Bug 报告（独立生命周期，见 bug-standard） |
| `tasks/test-cases/` | `TC-xxx` | 测试用例设计文档，先于实现创建 |
| `tasks/archive/done/` | — | 已完成的 REQ / BUG / TC |
| `tasks/archive/cancelled/` | — | 已废弃的 REQ / BUG / TC |

### 3.3 文档粒度

- `phases/`：一个 Phase 一份文档
- `features/`：一个需求项一份文档
- `bugs/`：一个 Bug 一份文档（不与 REQ 合并）
- `test-cases/`：一个需求项或 Bug 对应一份或多份测试用例文档
- `archive/done/` 和 `archive/cancelled/`：从各活跃目录移入，子目录区分完成和废弃

---

## 4. Phase 规范

### 4.1 Phase 文档用途

| 项目 | 内容 |
|---|---|
| 规则 | 每个 Phase 必须定义阶段目标、阶段范围、阶段外内容、入口条件和退出条件 |
| 目的 | 让 Agent 在认领具体任务前知道当前迭代边界 |
| 好示例 | `phase-2-manual-diagnosis.md` 明确只处理手动诊断，不处理自动轮询 |
| 坏示例 | Phase 名称存在，但没有 scope，导致 Agent 跨阶段随意实现 |

### 4.2 Phase 最低字段

- `phase_id`
- `title`
- `status`
- `goal`
- `in_scope`
- `out_of_scope`
- `exit_criteria`

---

## 5. 需求项规范

### 5.1 每个需求项必须包含的字段

| 字段 | 说明 |
|---|---|
| `req_id` | 唯一编号，例如 `REQ-001` |
| `title` | 简洁标题 |
| `status` | 只能使用本规范状态机 |
| `priority` | `P0` / `P1` / `P2` / `P3` |
| `phase` | 所属 Phase，例如 `phase-1` |
| `owner` | `unassigned` / `claude_code` / `openai_codex` |
| `depends_on` | 顺序依赖项列表（所有项必须 `done` 才可认领），无则空数组 |
| `test_case_ref` | 对应测试用例文档列表，例如 `[TC-001, TC-002]`；`test_designed` 状态必须非空 |
| `scope` | `frontend` / `backend` / `fullstack` / `docs` / `tests` |
| `acceptance` | 验收标准摘要（一句话）|

### 5.2 推荐文档结构

```md
---
req_id: REQ-001
title: [标题]
status: draft
priority: P1
phase: phase-1
owner: unassigned
depends_on: []
test_case_ref: []
scope: backend
acceptance: [一句话摘要]
---

# Goal

# In Scope

# Out of Scope

# Acceptance Criteria

# Test Case Design Notes
> 描述需要覆盖的场景，供测试用例设计者参考。此节不是测试用例本身，测试用例独立存在于 test-cases/。

# Agent Notes
```

### 5.3 一项需求只定义一个完成口径

| 项目 | 内容 |
|---|---|
| 规则 | 一个需求项必须只有一个“完成”判定，不得同时包含多个彼此独立的终点 |
| 目的 | 避免 Agent 做了一半就误判为完成 |
| 好示例 | “stop 接口返回 dropped_queue 且测试更新完成” |
| 坏示例 | “修后端 stop、修前端归档、补 5 个 unrelated E2E、重设计 UI” 全塞一项 |

---

## 6. 状态机

### 6.1 允许状态

| 状态 | 含义 |
|---|---|
| `draft` | 需求还在整理，不能认领 |
| `ready` | 已定义清楚，等待测试用例设计 |
| `test_designed` | 对应 TC 文档已创建并填入 `test_case_ref`，可被 Agent 认领实现 |
| `in_progress` | 已被某个 Agent 认领并执行中 |
| `blocked` | 由于依赖未完成或外部决策缺失而暂停；原因写入 `Agent Notes` |
| `review` | 实现已完成，PR 已提，等待 review / 验收 |
| `done` | 已合并或已确认完成 |

### 6.2 合法流转

```
draft → ready → test_designed → in_progress → review → done
                     ↓                ↓
                  blocked ←→ ready / test_designed
```

- `draft → ready`：需求范围、验收标准已确认
- `ready → test_designed`：TC 文档已创建，`test_case_ref` 非空
- `ready → blocked`：发现外部依赖缺失
- `test_designed → in_progress`：Agent 完成认领（branch + commit 原子操作）
- `test_designed → blocked`：认领前发现依赖未完成
- `in_progress → review`：实现完成，PR 已提
- `in_progress → blocked`：开发中发现阻塞
- `review → test_designed`：review 打回，需要修改后重提（保留 TC）
- `review → done`：PR 合并
- `blocked → ready` / `blocked → test_designed`：阻塞解除，根据 TC 是否已完成选择目标状态

### 6.3 非法流转

- 不允许 `draft → done`
- 不允许 `blocked → done`
- 不允许 `ready → in_progress`（必须经过 `test_designed`）
- 不允许 `test_case_ref` 为空时迁移到 `test_designed`
- 不允许两个 Agent 同时把同一项从 `test_designed` 改成 `in_progress`

---

## 7. 优先级规范

| 优先级 | 含义 | 处理原则 |
|---|---|---|
| `P0` | 阻断开发或高风险线上问题 | 优先于其他项 |
| `P1` | 当前 Phase 的核心交付 | 应优先认领 |
| `P2` | 重要但不阻断主路径 | 在 P0/P1 后处理 |
| `P3` | 低优先级改进或整理 | 可延期 |

### 7.1 Agent 默认认领顺序

1. `ready` 且未阻塞
2. 当前 Phase 内
3. 优先级从 `P0` 到 `P3`
4. 依赖最少、验收最明确的项优先

---

## 8. 多 Agent 自动认领规程

### 8.1 参与 Agent

| Agent | 标识 |
|---|---|
| Claude Code | `claude_code` |
| OpenAI Codex | `openai_codex` |

### 8.2 认领前检查

Agent 在认领需求前，必须依次确认：

- [ ] `status == test_designed`
- [ ] `owner == unassigned`
- [ ] `test_case_ref` 非空（TC 文档已存在于 `tasks/test-cases/`）
- [ ] `depends_on` 中所有项已 `done`
- [ ] 任务范围与自身当前上下文不冲突

### 8.3 认领规则（PR-as-Claim）

| 项目 | 内容 |
|---|---|
| 规则 | 认领必须通过创建工作分支 + 第一个 commit + **立即开 Draft PR** 完成，不得仅口头声明 |
| 分支命名 | `feat/REQ-001-<short-description>` |
| 第一个 commit | 只改 `tasks/features/REQ-xxx.md`：`owner` → 自身标识，`status` → `in_progress`；commit message：`claim: REQ-001` |
| Draft PR | 认领 commit push 后立即开 Draft PR，PR 标题包含 `REQ-xxx`——这是全局可见的认领信号 |
| 竞态处理 | Agent 认领前先用 `gh pr list --search "REQ-xxx"` 检查是否已有 PR；若已有则跳过该任务 |
| 好示例 | 分支已推送 + Draft PR 已开，任何人/Agent 均可见该任务已被认领 |
| 坏示例 | 仅创建本地分支未推送，或推送了分支但未开 PR——其他 Agent 无法感知 |

> **局限性说明**：纯分支名锁不是原子锁——两个 Agent 可用不同分支名认领同一任务。
> PR-as-Claim 通过 GitHub PR 列表作为共享可见状态解决此问题。
> 在当前 HITL 模式下（所有 PR 需人工 review），双认领最终会在 review 阶段被发现和解决。

### 8.4 放弃与释放

若 Agent 无法继续，必须：

- 把 `status` 改回 `test_designed`（TC 已有），或改为 `blocked`
- 清空 `owner` 回到 `unassigned`
- 在 `Agent Notes` 中简述原因
- 删除或关闭对应工作分支

### 8.5 分工规则

> 以 Agent 各自 SOUL.md 的 Task Scope 定义为准，本表是摘要。

| scope 字段 | 主责 Agent | 依据 |
|---|---|---|
| `frontend` | `claude_code` | SOUL.md：前端实现为主要能力 |
| `backend` | `claude_code` | SOUL.md：后端特性开发为主要能力 |
| `fullstack` | `claude_code` | SOUL.md：跨端实现 |
| `tests` | `claude_code` 或 `openai_codex` | TC 设计由 openai_codex 主导；测试代码实现由 claude_code |
| `docs` | `openai_codex` | SOUL.md：文档/一致性审查为主要能力 |

> `openai_codex` **不认领** `scope: backend/frontend/fullstack` 的实现任务——
> 其职责是 TC 设计、代码审查、Bug 上报，不是生产代码实现。
> 详见 `agents/openai-codex/SOUL.md`。

---

## 9. 依赖处理

### 9.1 depends_on 写法

| 项目 | 内容 |
|---|---|
| 语义 | 顺序依赖：`depends_on` 中所有项 `done` 后，当前项才可认领实现 |
| 规则 | 依赖必须写入 frontmatter，不能只在聊天里说明 |
| 好示例 | `depends_on: [REQ-003]`，且 REQ-003 已完成后再认领本项 |
| 坏示例 | `depends_on: []`，但实际上依赖另一个未完成项，导致实现冲突 |

### 9.2 阻塞处理

若任务进入 `blocked` 状态，原因必须写入 `Agent Notes`，格式：

```
blocked: [原因描述，例如"等待 PM 确认 API 字段设计" 或 "REQ-005 尚未完成"]
```

`blocked` 状态解除后，根据 `test_case_ref` 是否已填写，迁移到 `ready` 或 `test_designed`。

### 9.3 依赖项完成前禁止启动

- 若 `depends_on` 中存在非 `done` 项，则当前需求不得认领
- Agent 不得自行跳过依赖直接进入实现

---

## 10. 需求与实现同步规则

### 10.1 实现前（认领后，开始写代码前）

- [ ] 读 Phase 文档，确认当前阶段边界
- [ ] 读对应需求项，确认验收标准
- [ ] 读 `test_case_ref` 中所有 TC 文档，理解需要通过的测试场景
- [ ] 先写测试（或确认 TC 已可运行），再写实现

### 10.2 实现后（PR 提交时）

- [ ] 把需求项状态改为 `review`
- [ ] 更新 `Agent Notes`（说明实现要点、已知边界）
- [ ] 若范围变更，回写 `In Scope / Out of Scope`
- [ ] PR 描述中列出关联 TC 的通过情况

### 10.3 合并后

- [ ] 把需求项改为 `done`
- [ ] 将 `tasks/features/REQ-xxx.md` 移到 `tasks/archive/done/`
- [ ] 将关联的 `tasks/test-cases/TC-xxx.md` 同步移到 `tasks/archive/done/`
- [ ] 若影响阶段目标，更新对应 `phases/` 文档

---

## 11. 审查清单

### 自动可检查（脚本 / CI）

- [ ] 所有需求项 frontmatter 字段完整（含 `test_case_ref`）
- [ ] `status` 只使用允许枚举值
- [ ] `priority` 只使用 `P0/P1/P2/P3`
- [ ] `owner` 只使用 `unassigned/claude_code/openai_codex`
- [ ] `depends_on` 中的编号在 repo 中存在
- [ ] `status == test_designed` 时 `test_case_ref` 非空
- [ ] `test_case_ref` 中的 TC 文档在 `tasks/test-cases/` 中存在
- [ ] `status == in_progress` 时 `owner != unassigned`

### 人工检查

- [ ] 每个需求项范围足够小，可被单个 Agent 独立完成
- [ ] 验收标准明确，不依赖聊天上下文
- [ ] 状态流转真实反映当前进展
- [ ] 没有两个需求项描述同一件事

---

## 12. 验收标准

- **通过**：需求目录可作为 Agent 开发起点，状态、优先级、依赖和认领信息完整
- **打回**：
  - 缺关键 frontmatter 字段
  - 状态机不合法
  - 需求范围无法执行或验收标准不明确
  - 任务已被实现但需求未同步

---

## 13. 速查词汇表

| 标准术语 | 含义 | 禁用同义词 |
|---|---|---|
| Phase | 当前迭代阶段的范围与目标 | 里程碑（不加说明时） |
| 需求项 | 一个可独立认领、可验收的任务单元 | 大需求、随手任务 |
| Ready | 需求已定义清楚，等待测试用例设计 | 待做、可开始、todo |
| Test Designed | TC 文档已创建，可被 Agent 认领实现 | 测试写完了、可以开始了 |
| Blocked | 依赖未完成或外部决策缺失，原因在 Agent Notes | 暂缓、先放着 |
| Review | 实现完成、PR 已提，待验收 | done_pending、almost_done |
| Owner | 当前认领 Agent | assignee（不加说明时） |
| depends_on | 顺序依赖（技术或逻辑上必须先完成的项）| blocked_by（已移除）|

---

## 14. 变更日志

| 版本 | 日期 | 变更摘要 |
|---|---|---|
| 0.1 | 2026-03-12 | 初始版本；定义需求目录、状态机、优先级和 Claude Code / OpenAI Codex 双 Agent 认领规则 |
| 0.2 | 2026-03-12 | 新增 `test_designed` 状态，强制测试先行；引入 `test_case_ref` 字段；删除 `blocked_by`，统一使用 `depends_on`；目录重设计（features/bugs/test-cases/archive/done+cancelled）；认领机制改为 Branch-as-Lock；更新同步规则与审查清单 |
| 0.3 | 2026-03-12 | 根目录由 `requirements/` 重命名为 `tasks/`：Bug 在语义上是工作项而非规格说明，`tasks/` 对 Agent 更自然；子目录结构不变 |
| 0.4 | 2026-03-12 | Branch-as-Lock 升级为 PR-as-Claim（Draft PR 作为全局可见认领信号，需先查 `gh pr list --search REQ-xxx`）；修正 §8.5 分工表（openai_codex 不认领实现任务，与 SOUL.md 对齐） |
