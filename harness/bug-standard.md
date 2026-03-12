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
> Bug 与功能需求（REQ）生命周期独立，但共用同一套 Agent 认领机制和 Branch-as-Lock 规则。

---

## 1. 适用范围

- **组件**：Bug 报告、根因定位、回归测试、关闭口径
- **输入类型**：测试失败输出、人工发现缺陷、CI 失败、Canary 报警
- **触发时机**：
  - [ ] 测试用例运行失败时
  - [ ] 人工测试发现与预期不符的行为时
  - [ ] LLM Canary 结果偏离可接受范围时
  - [ ] PR review 中发现已合并代码存在缺陷时

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

### 3.1 目录位置

```text
requirements/bugs/BUG-xxx.md       # 活跃 Bug
requirements/archive/done/         # 已关闭 Bug
requirements/archive/cancelled/    # 已标记 wont_fix 的 Bug
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
- [ ] `related_req` 中涉及的 REQ 无正在进行的 `in_progress` 项（避免同时修改同一代码区域）

### 6.2 认领规则（Branch-as-Lock）

| 项目 | 内容 |
|---|---|
| 分支命名 | `fix/BUG-001-<short-description>` |
| 第一个 commit | 只改 `requirements/bugs/BUG-xxx.md`：`owner` → 自身标识，`status` → `in_progress` |
| commit message | `claim: BUG-001` |
| 竞态解决 | 同 requirement-standard §8.3，后 push 失败方重选其他 `confirmed` Bug |

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
