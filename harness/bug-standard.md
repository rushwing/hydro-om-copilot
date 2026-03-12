---
harness_id: BUG-STD-001
component: bugs / defect tracking
owner: Engineering
version: 0.1
status: draft
last_reviewed: 2026-03-12
---

# Harness Standard — Bug 管理与回归规程

> 本规范定义 Hydro O&M Copilot 在 Harness Engineering 范式下的 Bug 记录方式、
> 状态机、严重等级、Agent 自动认领与回归测试要求。
> 默认 Bug 协作走 GitHub；仅当缺陷需要长期跟踪或进入 Agent 自动修复队列时，才提升为 repo 内 Bug 工作项。

---

## 1. 适用范围

- **组件**：Bug 报告、根因定位、回归测试、关闭口径
- **输入类型**：测试失败输出、人工发现缺陷、CI 失败、Canary 报警
- **触发时机**：
  - [ ] 测试用例运行失败时
  - [ ] 人工测试发现与预期不符的行为时
  - [ ] LLM Canary 结果偏离可接受范围时
  - [ ] PR review 中发现已合并代码存在缺陷时

### 1.1 事实源边界

| 场景 | 默认事实源 |
|---|---|
| PR review 中发现的问题 | GitHub PR comment / review |
| CI 失败或临时缺陷协作 | GitHub issue / PR |
| 需要长期跟踪、与 REQ/TC 建强关联、或进入 Agent 自动修复队列 | `tasks/bugs/BUG-xxx.md` |

---

## 2. Bug 与需求的关系

| 场景 | 处理方式 |
|---|---|
| 已有 REQ，实现与验收标准不符 | 开 Bug，关联 `related_req`；REQ 状态不变 |
| REQ 验收标准本身写错导致 Bug | 开 Bug，同时更新 REQ 的 `Acceptance Criteria` 和对应 TC |
| 没有对应 REQ 的缺陷（技术债/框架问题）| 开 Bug，`related_req: []` |
| Bug 修复需要引入新功能 | Bug 关闭后单独开 REQ，不在 Bug 内扩展 |

---

## 3. 目录与文档规范

> 本节仅适用于 Bug 被提升为 repo 内工作项时。

### 3.1 目录位置

```text
tasks/bugs/BUG-xxx.md       # 活跃 Bug
tasks/archive/done/         # 已关闭 Bug
tasks/archive/cancelled/    # 已标记 wont_fix 的 Bug
```

### 3.2 Bug 文档必须包含的字段

| 字段 | 说明 |
|---|---|
| `bug_id` | 唯一编号，例如 `BUG-001` |
| `title` | 简洁标题，动词开头，例如"SSE 断流后 session log 未清理" |
| `status` | 只能使用本规范状态机 |
| `severity` | `S1` / `S2` / `S3` / `S4`（见 §4） |
| `priority` | `P0` / `P1` / `P2` / `P3` |
| `owner` | `unassigned` / `claude_code` / `openai_codex` |
| `related_req` | 关联需求编号列表，无则空数组 |
| `related_tc` | 触发此 Bug 的测试用例，或回归时需新增的 TC |
| `reported_by` | `human` / `ci` / `canary` / Agent 标识 |
| `depends_on` | （可选）必须先合并的 REQ/BUG 编号列表，无则省略或空数组；用于 Serialize 策略，Agent 看到此字段时不认领 |

### 3.3 Bug 文档推荐结构

```md
---
bug_id: BUG-001
title: [动词开头的简洁标题]
status: open
severity: S2
priority: P1
owner: unassigned
related_req: []
related_tc: []
reported_by: human
depends_on: []
---

# 现象描述
> 实际发生了什么，在什么操作路径下触发

# 预期行为
> 按需求/验收标准，应该发生什么

# 复现步骤
1.
2.
3.

# 环境信息
- 分支：
- 相关 commit：

# 根因分析
> 修复者填写；定位到具体文件/函数/逻辑

# 修复方案
> 修复者填写；说明改动范围

# 回归测试
> 对应 TC 编号，或新增 TC 的描述；必须在 PR 中通过

# Agent Notes
```

---

## 4. 严重等级

| 等级 | 含义 | 典型示例 |
|---|---|---|
| `S1` | 系统不可用或核心功能完全失效 | 后端启动失败；诊断接口 500；SSE 永不返回 |
| `S2` | 主要功能损坏，有明显错误结果 | 诊断结果丢失字段；历史归档逻辑错误 |
| `S3` | 次要功能异常，有替代路径 | UI 显示错位；非关键字段格式错误 |
| `S4` | 体验问题，不影响功能 | 文案错别字；颜色偏差；日志冗余 |

### 4.1 严重等级与优先级的关系

严重等级描述**影响范围**，优先级描述**处理顺序**。两者独立：

| 场景 | severity | priority |
|---|---|---|
| 启动失败（阻断所有人） | S1 | P0 |
| 历史页偶发数据错误（影响用户但有刷新绕过）| S2 | P1 |
| 深色模式颜色偏差（不影响读取）| S4 | P3 |

---

## 5. 状态机

### 5.1 允许状态

| 状态 | 含义 |
|---|---|
| `open` | Bug 已记录，等待确认 |
| `confirmed` | 已确认可复现，等待认领修复 |
| `in_progress` | 已被 Agent 认领并执行修复中 |
| `fixed` | 修复代码已提交 PR |
| `regressing` | PR 合并后正在运行回归测试 |
| `closed` | 回归测试通过，Bug 已关闭 |
| `wont_fix` | 明确决策不修复（需注明原因）|

### 5.2 合法流转

```
open → confirmed → in_progress → fixed → regressing → closed
         ↓               ↓
      wont_fix      wont_fix（开发中发现不值得修）
                         ↓
                    open（修复方案不可行，重新评估）
```

- `open → confirmed`：能稳定复现，已确认是 Bug 而非设计如此
- `confirmed → in_progress`：Agent 认领（Branch-as-Lock，见 §6）
- `in_progress → fixed`：PR 已提，包含修复代码和回归 TC
- `fixed → regressing`：PR 合并，CI 开始跑回归
- `regressing → closed`：回归测试全通过
- `regressing → in_progress`：回归测试失败，需继续修复
- `* → wont_fix`：任何阶段决策不修复，原因写入 `Agent Notes`

### 5.3 非法流转

- 不允许 `open → closed`（必须经过 confirmed 和回归）
- 不允许 `fixed → closed`（必须经过 `regressing`，确保回归测试跑过）
- 不允许 PR 中无回归 TC 而将状态推进到 `fixed`

---

## 6. Agent 认领规程

### 6.1 认领前检查

- [ ] `status == confirmed`
- [ ] `owner == unassigned`
- [ ] `related_req` 中涉及的 REQ 无正在进行的 `in_progress` 项（避免同时修改同一代码区域）；
  **例外**：若采用 Stacked PR 策略（fix PR base 指向 REQ 分支），允许 related_req 处于 `in_progress`（见 agent-cli-playbook.md §Stacked PR）

### 6.2 认领规则（仅 repo 内 Bug 适用）

认领采用与 REQ 实现相同的 **Claim PR mutex**，分两阶段执行：

**阶段一：Claim PR（获取锁）**

| 项目 | 内容 |
|---|---|
| 分支命名 | `claim/BUG-001` |
| commit 内容 | 只改 `tasks/bugs/BUG-xxx.md`：`owner` → 自身标识，`status` → `in_progress` |
| commit message | `claim: BUG-001` |
| PR 标题 | `claim: BUG-001` |
| 合并方式 | 开 PR 后立即 `gh pr merge --auto --squash`，等待 CI 通过后自动合并 |
| 竞态解决 | 若 PR 因冲突（另一 Agent 已 claim）合并失败 → 停止，不认领 |

**阶段二：修复 PR（在 claim 合并后）**

| 项目 | 内容 |
|---|---|
| 分支命名 | `fix/BUG-001-<short-description>` |
| 基于 | `main`（标准）；Stacked PR 时见下方例外 |
| 竞态保证 | Claim PR 已合并 = 锁已获取，直接开发，无需再次修改 BUG-xxx.md 的 owner/status |

**例外一：Bundle（同一特性内的 Bug）**

当 Bug 属于正在实现的同一特性、且修复应合入已有的 `feat/REQ-xxx` PR 时，**不使用 Claim PR mutex**，改为：

1. `git checkout feat/REQ-xxx-...`
2. 第一个 commit 只改 `tasks/bugs/BUG-xxx.md`：`owner` → 自身标识，`status` → `in_progress`，commit message `claim: BUG-001`
3. 继续在同一分支上实现修复，最终 commit 将 status 改为 `fixed`
4. 修复随 REQ PR 一起 review 和合并，不开独立 PR

> 竞态说明：REQ 分支已被 REQ 的认领 Agent 持有，同一时间不会有其他 Agent 操作该分支，无需额外 mutex。

**例外二：Stacked PR（fix 分支基于依赖分支）**

Stacked PR 的 fix 分支从 `<stacked_base>` 切出。Claim PR 正常合并到 `main`，**不对 `<stacked_base>` 做任何写操作**（不 cherry-pick、不推送），因为该分支由 REQ Agent 持有。

流程：

1. 按标准流程完成 Claim PR（合并到 `main`）
2. `git fetch origin && git checkout <stacked_base> && git checkout -b fix/BUG-001-<desc>`
   — fix 分支上 `BUG-xxx.md` 此时显示 `status: confirmed`（来自依赖分支，非 `in_progress`），这是预期的
3. 开发修复 + 回归测试
4. 最终 commit：将 `BUG-xxx.md` 的 `status` 从 `confirmed` 改为 `fixed`（直接推进，跳过 `in_progress` 转换）
5. 开 PR，base 指向 `<stacked_base>`

> **retarget 时的冲突处理**：当 `<stacked_base>` merge 到 main 后，fix PR retarget 到 main，
> `BUG-xxx.md` 会产生一行冲突（main 一侧为 `in_progress`，fix 分支一侧为 `fixed`）。
> HITL reviewer 解决冲突时保留 `status: fixed` 即可。这是 Stacked PR 拓扑的已知代价，
> 优于向他人持有的共享分支写入提交。

### 6.3 修复完成要求

PR 必须同时包含：

- [ ] Bug 修复代码
- [ ] 回归测试用例（新增或更新 TC 文档，写入 `related_tc`）
- [ ] `BUG-xxx.md` 状态更新为 `fixed`，填写"根因分析"和"修复方案"

### 6.4 放弃与释放

- 把 `status` 改回 `confirmed`
- 清空 `owner`
- 在 `Agent Notes` 中说明原因

---

## 7. 回归测试要求

### 7.1 最低要求

每个 Bug 修复 PR **必须包含至少一个能复现并验证修复的测试**：

| Bug 层级 | 回归测试类型 |
|---|---|
| 后端逻辑 / API 契约 | pytest 集成测试（Layer 2） |
| 前端组件行为 | Vitest 组件测试 |
| 用户流程 | Playwright E2E（仅 S1/S2）|
| LLM 输出结构 | Canary 样本更新（仅 LLM 相关 Bug）|

### 7.2 禁止事项

- 禁止在没有新增或更新测试的情况下关闭 Bug
- 禁止用"手工验证了"替代自动化回归测试（S4 Bug 除外，可豁免）

---

## 8. 关闭口径

| 状态 | 关闭条件 |
|---|---|
| `closed` | 回归测试在 CI 中全通过；`related_tc` 非空；`根因分析` 已填写 |
| `wont_fix` | 已写明不修复原因；若为设计如此，应更新 REQ 的 Acceptance Criteria |

---

## 9. 审查清单

### 自动可检查（脚本 / CI）

- [ ] Bug frontmatter 字段完整
- [ ] `status` 只使用允许枚举值
- [ ] `severity` 只使用 `S1/S2/S3/S4`
- [ ] `priority` 只使用 `P0/P1/P2/P3`
- [ ] `status == fixed` 时 `related_tc` 非空
- [ ] `status == in_progress` 时 `owner != unassigned`
- [ ] `related_req` 中编号在 repo 中存在

### 人工检查

- [ ] 复现步骤明确，另一个人能独立复现
- [ ] 根因分析定位到具体代码位置
- [ ] 回归 TC 能精准覆盖 Bug 场景，而非泛化测试
- [ ] `wont_fix` 有充分理由，相关 REQ / TC 已同步更新

---

## 10. 速查词汇表

| 标准术语 | 含义 | 禁用同义词 |
|---|---|---|
| Bug | 与验收标准或预期行为不符的缺陷 | Issue、问题（不加说明时） |
| Confirmed | 可复现，已确认是 Bug | 已知问题、看起来是 Bug |
| Regressing | 修复已合并，回归测试运行中 | 测试中、验证中 |
| Wont Fix | 明确不修复的决策 | 暂缓、低优先级（不加说明时） |
| related_tc | 回归此 Bug 的测试用例 | 相关测试 |

---

## 11. 变更日志

| 版本 | 日期 | 变更摘要 |
|---|---|---|
| 0.1 | 2026-03-12 | 初始版本；定义 Bug 状态机、严重等级、Agent 认领规程、回归测试要求与关闭口径 |
| 0.2 | 2026-03-12 | 目录路径由 `requirements/` 更新为 `tasks/` |
| 0.3 | 2026-03-13 | §6.2 认领规则改为 Claim PR mutex 两阶段流程，与 requirement-standard 和 agent-cli-playbook 模板 C 保持一致 |
| 0.4 | 2026-03-13 | §6.2 补充 Bundle 例外（claim commit 提交到 REQ 分支，无 Claim PR）和 Stacked PR 例外（不写共享分支；retarget 时 HITL 解决冲突保留 fixed）|
