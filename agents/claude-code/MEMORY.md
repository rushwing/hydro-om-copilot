---
agent_id: claude_code
type: memory-index
budget: 100 lines max (enforce on every write)
last_updated: 2026-03-15
---

# Claude Code — Memory Index

> **读取规则**：每次会话读 Gotchas（全部）+ Lessons/Deliveries 的标题行。
> 只有当标题与当前任务相关时，才读 `→ detail` 链接的完整文件。
> 超过 100 行时，将最久未引用的 Lessons 移至 `memories/archive/`。

---

## Gotchas
> 每次开发都可能踩的项目专属陷阱。严格 ≤10 条，每条 1 行。

- **httpx ≥ 0.28**：`AsyncClient` 不接受 `app=`，用 `ASGITransport(app=app)`
- **冻结文件**：`diagnosisStore.ts` / `useSSEDiagnosis.ts` / `useSessionHistory.ts` / `diagnosisApi.ts` / `diagnosis.ts` 不可修改
- **深色主题**：必须本地定义 `darkRiskColors`，禁用 `riskLevelColor`
- **LangGraph stub**：用 `app.dependency_overrides[get_graph]`，不用 `monkeypatch.setattr`
- **Retriever patch**：stub 点是 `app.agents.retrieval.get_retriever`，`deps.py` 中不存在此符号
- **嵌入模型**：测试中 patch retriever，禁止加载 4GB 本地模型
- **`unit_id`**：纯字符串（如 `"#1机"`），不是数字 ID
- **`AUTO_RANDOM_PROBLEMS_GEN`**：测试环境必须为 `false`，否则后台轮询污染状态
- **拉新分支**：先 `git fetch origin` + 确认上一个 PR 已合入 main，再 `checkout main && pull` 后拉分支；不可直接从旧功能分支分叉

---

## Lessons
> 排查 >30 分钟或反直觉的决策。每条 ≤3 行；超过 3 行提取到 `memories/L-xxx.md`。

<!-- 格式：
### L-xxx · [标题] · YYYY-MM-DD
**Lesson**: 一句话结论
**Apply when**: 触发条件
→ [detail](memories/L-xxx.md)   ← 只在有详细文件时才写这行
-->

### L-001 · 新分支必须基于最新 main · 2026-03-15
**Lesson**: 从旧功能分支拉新分支会带入已合入 main 的旧提交，导致 force push 修复。
**Apply when**: 每次开始新 REQ 实现前——即便上一个 PR "应该已经合入"，也要主动 fetch 确认。

---

## Deliveries
> 重大功能/重构的关键决策。只记录"为什么这样做"，不记录进度。每条 ≤2 行。

<!-- 格式：
### D-xxx · [交付标题] · YYYY-MM-DD
**Key decision**: 最重要的一个决策及原因（影响未来类似工作）
-->

_（暂无记录）_

---

## Archive Index
> 移出主索引的历史条目。不在会话启动时加载。

→ [memories/archive/](memories/archive/)
