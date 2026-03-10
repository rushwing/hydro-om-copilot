# CLAUDE.md — Hydro O&M AI Copilot

水电机组异常诊断辅助系统。用户描述故障现象，AI 返回根因分析、SOP 检查清单和运维报告草稿。

---

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 18 + Vite + TypeScript + Tailwind CSS v3 |
| 状态 | Zustand |
| 后端 | FastAPI + LangGraph + LangChain + Python 3.11 |
| LLM | claude-sonnet-4-6 (temperature=0.1) |
| 向量存储 | ChromaDB（dev） / Qdrant（prod） |
| 嵌入 | BAAI/bge-large-zh-v1.5（本地，1024维）|
| 重排序 | BAAI/bge-reranker-v2-m3 |
| 包管理 | `uv`（后端）/ `npm`（前端）|

---

## 关键文件路径

- `backend/app/main.py` — FastAPI 入口，lifespan 挂载 retriever
- `backend/app/config.py` — Pydantic Settings（读 .env）
- `backend/app/agents/graph.py` — LangGraph StateGraph 入口
- `backend/app/agents/state.py` — AgentState TypedDict
- `backend/app/rag/hybrid_retriever.py` — BM25+Dense RRF 融合检索
- `backend/app/utils/prompts.py` — 所有 LLM 提示词（中文）
- `backend/app/api/routes/diagnosis.py` — SSE 路由
- `frontend/src/hooks/useSSEDiagnosis.ts` — SSE 生命周期管理
- `frontend/src/store/diagnosisStore.ts` — Zustand 全局状态
- `scripts/ingest_kb.py` — 知识库入库入口

---

## 架构约束（不可修改文件）

| 文件 | 原因 |
|------|------|
| `frontend/src/store/diagnosisStore.ts` | 全局状态契约；`riskLevelColor` 为浅色类，深色组件需本地定义 |
| `frontend/src/hooks/useSSEDiagnosis.ts` | SSE 生命周期，修改有副作用风险 |
| `frontend/src/hooks/useSessionHistory.ts` | localStorage 持久化逻辑 |
| `frontend/src/services/diagnosisApi.ts` | SSE 解析客户端 |
| `frontend/src/types/diagnosis.ts` | TS 类型定义，镜像后端 Pydantic 模型 |

**深色主题必须本地定义 `darkRiskColors`（不可用 `riskLevelColor`）：**

```typescript
const darkRiskColors: Record<RiskLevel, string> = {
  low: "text-emerald-400 bg-emerald-950 border-emerald-800",
  medium: "text-amber bg-amber-950 border-amber-800",
  high: "text-orange-400 bg-orange-950 border-orange-800",
  critical: "text-red-400 bg-red-950 border-red-800 critical-pulse",
};
```

**`DiagnosisRequest`**：`unit_id` 是纯字符串（如 `"#1机"`），不是数字 ID。

---

## Agent 流程

```
symptom_parser → [image_agent?] → retrieval → reasoning → report_gen
```

topic 键：`vibration_swing` / `governor_oil_pressure` / `bearing_temp_cooling`

---

## 开发快速命令

```bash
bash scripts/local/env-setup.sh   # 初始化环境（仅需一次）
bash scripts/local/ingest.sh      # 知识库入库
bash scripts/local/dev.sh         # 后端 :8000 + 前端 :5173
bash scripts/local/test.sh        # pytest + tsc + ESLint
bash scripts/local/build.sh       # ruff → tsc → ESLint → vite build
```

Lint：`cd frontend && npm run lint` | `uv tool run ruff check backend/`

---

## 关键环境变量

```bash
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-sonnet-4-6
VECTOR_STORE_TYPE=chroma          # chroma | qdrant
EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
CORS_ORIGINS=http://localhost:5173
LANGCHAIN_TRACING_V2=false        # 生产环境默认禁用
```

---

## 任务→文档路由

| 任务类型 | 读此文档 |
|---------|---------|
| 技术选型、Lint 工具链、架构 scale-up | `docs/01-tech-stack.md` |
| 修改 LangGraph 节点、AgentState、节点路由 | `docs/02-langgraph-architecture.md` |
| RAG 检索、知识库结构、frontmatter schema | `docs/03-rag-kb-design.md` |
| SSE 流式实现、diagnosis.py 事件、stream_tokens | `docs/04-sse-streaming.md` |
| LangSmith 追踪、可观测性、eval 接入 | `docs/05-langsmith-integration.md` |
| 前端组件样式、UI 组件、Tailwind 颜色/字体 | `docs/06-frontend-design-system.md` |
| 构建脚本、Docker、docker-compose、K8s | `docs/07-build-deploy.md` |

---

## 常见问题

**Q: `uv run ruff` 找不到** → 用 `uv tool run ruff`

**Q: 风险徽章颜色在深色背景不可见** → 不用 `riskLevelColor`，用组件本地 `darkRiskColors`

**Q: 后端容器启动超时** → 首次需下载 ~4GB 嵌入模型，挂载 `models_cache` 卷后重启秒级完成
