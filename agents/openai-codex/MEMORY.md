---
agent_id: openai_codex
type: memory-index
budget: 100 lines max (enforce on every write)
last_updated: 2026-03-12
---

# OpenAI Codex — Memory Index

> **读取规则**：每次会话读 Gotchas（全部）+ Lessons/Deliveries 的标题行。
> 只有当标题与当前任务相关时，才读 `→ detail` 链接的完整文件。
> 超过 100 行时，将最久未引用的 Lessons 移至 `memories/archive/`。

---

## Gotchas
> 每次 review / TC 设计都可能踩的项目专属陷阱。严格 ≤10 条，每条 1 行。

- **SSE 格式**：`diagnosisApi.ts` 用 `\n\n` 分隔解析；mock 必须返回正确格式文本 fixture
- **Pydantic ↔ TS 对齐**：`backend/app/models/` 字段变更必须同步到 `frontend/src/types/diagnosis.ts`
- **深色主题**：检查新组件是否遗漏本地 `darkRiskColors` 定义
- **`AUTO_RANDOM_PROBLEMS_GEN`**：测试环境必须 `false`，否则后台轮询干扰状态机
- **依赖注入**：路由层用 `Depends(get_graph)`，测试必须用 `dependency_overrides`，不是 monkeypatch

---

## Lessons
> TC 设计模式或 review 发现的高价值规律。每条 ≤3 行；超过 3 行提取到 `memories/L-xxx.md`。

<!-- 格式：
### L-xxx · [标题] · YYYY-MM-DD
**Lesson**: 一句话结论
**Apply when**: 触发条件
→ [detail](memories/L-xxx.md)   ← 只在有详细文件时才写这行
-->

_（暂无记录）_

---

## Deliveries
> 重大 TC 设计或 review 发现的关键模式。每条 ≤2 行。

<!-- 格式：
### D-xxx · [交付标题] · YYYY-MM-DD
**Key decision**: 最重要的一个决策及原因
-->

_（暂无记录）_

---

## Archive Index
> 移出主索引的历史条目。不在会话启动时加载。

→ [memories/archive/](memories/archive/)
