---
agent_id: claude_code
type: memory
last_updated: 2026-03-12
---

# Claude Code — Project Memory

> 记录重大交付、架构决策和经验教训。
> 新会话启动时读此文件，避免重复犯错，继承项目智慧。
> 更新规则：每次 Delivery（PR merge）后，将值得记录的内容追加到对应章节。

---

## Significant Deliveries

<!-- 格式：
### REQ-xxx · [标题] · YYYY-MM-DD
简述：做了什么
关键决策：为什么这样做
-->

_（暂无记录，首次交付后填入）_

---

## Architecture Decisions

<!-- 格式：
### [决策标题] · YYYY-MM-DD
背景：...
决策：...
替代方案及否决原因：...
-->

_（暂无记录）_

---

## Lessons Learned

<!-- 格式：
### [教训标题] · YYYY-MM-DD
事件：...
根因：...
避免方式：...
-->

_（暂无记录）_

---

## Known Constraints & Gotchas

> 长期有效的项目专属陷阱，每次会话都应记住。

- **冻结文件**：`diagnosisStore.ts`、`useSSEDiagnosis.ts`、`useSessionHistory.ts`、`diagnosisApi.ts`、`diagnosis.ts` 不可修改
- **深色主题**：必须本地定义 `darkRiskColors`，禁用 `riskLevelColor`
- **httpx ≥ 0.28**：`AsyncClient` 不接受 `app=` 参数，必须用 `ASGITransport(app=app)`
- **嵌入模型**：测试中必须 patch `app.agents.retrieval.get_retriever`，禁止加载 4GB 模型
- **LangGraph stub**：用 `app.dependency_overrides[get_graph]`，不用 `monkeypatch.setattr`
- **`unit_id`**：是纯字符串（如 `"#1机"`），不是数字 ID
