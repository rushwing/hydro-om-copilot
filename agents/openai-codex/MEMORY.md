---
agent_id: openai_codex
type: memory
last_updated: 2026-03-12
---

# OpenAI Codex — Project Memory

> 记录重大 TC 设计决策、审查发现和经验教训。
> 新会话启动时读此文件，避免重复遗漏，继承审查智慧。
> 更新规则：每次完成 TC 设计或重大 code review 后追加。

---

## Significant TC Designs

<!-- 格式：
### TC-xxx · [标题] · YYYY-MM-DD
覆盖场景：...
设计决策：为什么选这几个场景
未覆盖（及原因）：...
-->

_（暂无记录，首次 TC 设计后填入）_

---

## Code Review Findings

<!-- 记录有代表性的 review 发现，帮助未来 review 更高效
格式：
### [发现标题] · YYYY-MM-DD · REQ/BUG-xxx
问题：...
Pattern：这类问题在哪些地方容易出现
-->

_（暂无记录）_

---

## Lessons Learned

_（暂无记录）_

---

## Known Review Checklist (Project-Specific)

> 本项目特有的审查要点，通用要点见 harness/review-standard.md。

- **SSE 解析**：`diagnosisApi.ts` 用 `\n\n` 分隔解析，mock 时必须返回正确格式的文本 fixture
- **Pydantic ↔ TS 对齐**：`backend/app/models/` 的字段变更必须同步到 `frontend/src/types/diagnosis.ts`
- **依赖注入**：路由层通过 `Depends(get_graph)` 注入图，测试必须用 `dependency_overrides`
- **AUTO_RANDOM_PROBLEMS_GEN**：测试环境必须为 `false`，否则后台轮询污染测试状态
- **深色主题一致性**：检查新组件是否遗漏 `darkRiskColors` 本地定义
