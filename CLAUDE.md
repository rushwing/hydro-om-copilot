# CLAUDE.md — Hydro O&M AI Copilot

开发者（和 AI 工具）快速参考。阅读本文件后可独立在此代码库中完成任务。

---

## 项目概述

水电机组异常诊断辅助系统。用户描述故障现象，AI 返回根因分析、SOP 检查清单和运维报告草稿。

**定位**：辅助诊断，不替代工程师判断。当前版本聚焦三个故障域：振动/摆度、调速器油压、轴承温升。

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

## 目录结构

```
hydro-om-copilot/
├── backend/
│   ├── app/
│   │   ├── agents/         # LangGraph 节点：graph.py, state.py, symptom_parser.py …
│   │   ├── api/routes/     # FastAPI 路由：diagnosis.py, health.py
│   │   ├── models/         # Pydantic 模型：request.py, response.py
│   │   ├── rag/            # 检索：hybrid_retriever.py, bm25_index.py, chunker.py …
│   │   ├── utils/          # prompts.py（所有 LLM 提示词）, streaming.py
│   │   ├── config.py       # Pydantic Settings（读 .env）
│   │   └── main.py         # FastAPI 入口，lifespan 挂载 retriever
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/diagnosis/   # InputPanel, StreamingOutput, RootCauseCard …
│   │   ├── hooks/                  # useSSEDiagnosis.ts, useSessionHistory.ts
│   │   ├── pages/                  # DiagnosisPage.tsx, HistoryPage.tsx
│   │   ├── services/               # diagnosisApi.ts（SSE 客户端）
│   │   ├── store/                  # diagnosisStore.ts（Zustand）
│   │   └── types/                  # diagnosis.ts（TypedDict 镜像）
│   ├── eslint.config.js
│   ├── tailwind.config.ts
│   └── tsconfig.json
├── scripts/
│   ├── ingest_kb.py        # 知识库入库脚本
│   ├── validate_kb.py      # YAML 元数据校验
│   ├── local/              # 本地开发脚本（env-setup / build / dev / test / ingest）
│   ├── docker/             # Docker 构建与部署脚本（build / push / deploy-compose / deploy-k8s）
│   └── k8s/                # Kubernetes 清单（kustomize base，namespace hydro-om）
├── docs/                   # 架构文档
├── docker-compose.yml      # 开发用（热重载 + build:）
├── docker-compose.prod.yml # 生产用（预构建镜像 + Qdrant v1.11.0）
└── .env.example
```

---

## 开发命令

### 推荐：使用脚本（详见 `docs/07-build-deploy.md`）

```bash
# 1. 环境初始化（仅需一次）
bash scripts/local/env-setup.sh    # 检查依赖 + 创建 .env + uv sync + npm install

# 2. 知识库入库
bash scripts/local/ingest.sh       # 支持 --reset / --kb-dir

# 3. 启动开发服务器
bash scripts/local/dev.sh          # 后端 :8000 + 前端 :5173，CTRL-C 同时终止

# 4. 测试
bash scripts/local/test.sh         # pytest + tsc + ESLint；支持 --backend-only / --frontend-only

# 5. 生产构建（含 lint）
bash scripts/local/build.sh        # ruff → tsc → ESLint → vite build
```

### 手动命令（底层）

```bash
# 后端
cd backend
uv sync                    # 安装依赖
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 前端
cd frontend
npm install
npm run dev                # Vite dev server → localhost:5173
npm run build              # tsc + vite build → dist/
npm run type-check         # tsc --noEmit
npm run lint               # ESLint

# 知识库
cd backend
uv run python ../scripts/validate_kb.py   # 校验 YAML 元数据
uv run python ../scripts/ingest_kb.py     # 入库
uv run python ../scripts/ingest_kb.py --reset  # 清空重建
```

### Docker 构建与部署

```bash
# 构建 CentOS Stream 9 镜像（打 git-sha + semver + latest 三个 tag）
bash scripts/docker/build.sh
REGISTRY=registry.example.com/hydro bash scripts/docker/build.sh  # 带 registry 前缀

# 推送镜像
REGISTRY=registry.example.com/hydro bash scripts/docker/push.sh

# docker-compose 生产部署（使用 docker-compose.prod.yml）
bash scripts/docker/deploy-compose.sh up      # 启动
bash scripts/docker/deploy-compose.sh logs    # 跟踪日志
bash scripts/docker/deploy-compose.sh ingest  # 容器内入库

# Kubernetes 部署
kubectl create secret generic hydro-om-secrets \
  --namespace hydro-om --from-literal=ANTHROPIC_API_KEY=sk-ant-...
REGISTRY=registry.example.com/hydro IMAGE_TAG=<git-sha> \
  bash scripts/docker/deploy-k8s.sh apply
bash scripts/docker/deploy-k8s.sh status          # 查看 Pod/Service 状态
bash scripts/docker/deploy-k8s.sh rollout-status  # 等待滚动更新完成
```

---

## Lint 命令

```bash
# 前端
cd frontend && npm run lint

# 后端（从项目根目录）
uv tool run ruff check backend/
uv tool run ruff check --fix backend/   # 自动修复
```

---

## 架构约束（不可修改文件）

以下文件受架构保护，**不得修改**：

| 文件 | 原因 |
|------|------|
| `frontend/src/store/diagnosisStore.ts` | 定义全局状态契约；`riskLevelColor` 导出浅色主题类，组件需本地定义深色版本 |
| `frontend/src/hooks/useSSEDiagnosis.ts` | SSE 生命周期管理，修改有副作用风险 |
| `frontend/src/hooks/useSessionHistory.ts` | localStorage 持久化逻辑 |
| `frontend/src/services/diagnosisApi.ts` | SSE 解析客户端 |
| `frontend/src/types/diagnosis.ts` | TypeScript 类型定义，镜像后端 Pydantic 模型 |

### `DiagnosisRequest` 类型

```typescript
interface DiagnosisRequest {
  session_id?: string;
  unit_id?: string;   // 纯字符串，如 "#1机"，不是数字 ID
  query: string;
  image_base64?: string;
}
```

### `riskLevelColor` 不可直接用于深色主题

`diagnosisStore.ts` 导出的 `riskLevelColor` 是浅色 Tailwind 类（`text-green-700 bg-green-100` 等）。
深色主题组件（`RiskBadge`, `HistoryPage`）必须本地定义：

```typescript
const darkRiskColors: Record<RiskLevel, string> = {
  low: "text-emerald-400 bg-emerald-950 border-emerald-800",
  medium: "text-amber bg-amber-950 border-amber-800",
  high: "text-orange-400 bg-orange-950 border-orange-800",
  critical: "text-red-400 bg-red-950 border-red-800 critical-pulse",
};
```

---

## Agent 流程

```
symptom_parser → [image_agent?] → retrieval → reasoning → report_gen
```

- `image_agent` 仅在 `state.image_base64` 非空时执行（条件边）
- `retrieval` 并行查询三个语料库（procedure / rule / case）
- 所有节点返回 partial state，不做全量覆盖
- 节点入口文件：`backend/app/agents/graph.py`

### topic 键 → 知识库覆盖

| topic 键 | 对应知识库文档 |
|----------|--------------|
| `vibration_swing` | `L2.TOPIC.VIB.001` |
| `governor_oil_pressure` | `L2.TOPIC.GOV.001` |
| `bearing_temp_cooling` | `L2.TOPIC.BEAR.001` |
| 所有 topic | `L1.ROUTER.001` + `L1.OVERVIEW.001` + `L2.SUPPORT.RULE.001` + `L2.SUPPORT.CASE.001` |

### 语料库 → 集合映射

| 语料库 | 包含 doc_id |
|--------|------------|
| `procedure` | `L2.TOPIC.VIB.001`, `L2.TOPIC.GOV.001`, `L2.TOPIC.BEAR.001`, `L1.ROUTER.001`, `L1.OVERVIEW.001` |
| `rule` | `L2.SUPPORT.RULE.001` |
| `case` | `L2.SUPPORT.CASE.001` |

---

## 前端设计系统要点

详见 `docs/06-frontend-design-system.md`，摘要：

- **主题**：暗色工业 HMI（`#0a0f1a` 背景，`#f59e0b` 琥珀色 accent）
- **字体**：`font-display`=Rajdhani，`font-sans`=Noto Sans SC，`font-mono`=JetBrains Mono
- **布局**：双列（`5/12` 左侧输入 + `7/12` 右侧结果），高度 `calc(100vh-52px)`
- **动画**：`.scan-line`（流式输出），`.node-active`（当前节点），`.animate-result`（结果模块出现）

---

## 环境变量（`.env`）

关键变量（完整列表见 `.env.example`）：

```bash
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-sonnet-4-6
LLM_TEMPERATURE=0.1

VECTOR_STORE_TYPE=chroma            # chroma | qdrant
CHROMA_PERSIST_DIR=./knowledge_base/vector_store

EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
RERANKER_MODEL=BAAI/bge-reranker-v2-m3

KB_DOCS_DIR=./knowledge_base/docs_internal
CORS_ORIGINS=http://localhost:5173

# LangSmith 追踪（生产环境默认禁用，数据合规审批后方可开启）
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=ls__...
```

---

## 知识库结构

四层体系（L0–L3），YAML frontmatter 元数据（以下为实际契约字段）：

```yaml
---
doc_id: L2.TOPIC.VIB.001
doc_level: L2
knowledge_type: topic_guide
domain: hydro_om_copilot
route_keys:
  - vibration_swing       # 首个 key 对应 TOPIC_KEYWORDS 字典键
  - vibration_frequency
upstream_docs:
  - L1.ROUTER.001
downstream_docs:
  - L2.SUPPORT.RULE.001
  - L3.SITE.001
site_stub_refs:
  - L3.SITE.001
---
```

必填字段：`doc_id`、`doc_level`、`knowledge_type`、`domain`、`route_keys`。
`upstream_docs`、`downstream_docs`、`site_stub_refs` 推荐填写，`title`/`version` 可选附加但不纳入系统校验逻辑。

`doc_id` 前缀用于前端知识库来源颜色编码：
- `L1.*` → 蓝色
- `L2.TOPIC.*` → 琥珀色
- `L2.SUPPORT.RULE.*` → 红色
- `L2.SUPPORT.CASE.*` → 绿色

---

## 代码规范

### TypeScript
- 严格模式（`"strict": true`）
- 导入路径别名：`@/` → `src/`
- `tsconfig.json` 包含 `"types": ["vite/client"]`（`import.meta.env` 支持）

### Python
- 目标版本 Python 3.11
- `Optional[X]` 写为 `X | None`（UP045，ruff 强制）
- `Iterator` 从 `collections.abc` 导入（UP035，ruff 强制）
- 不用 `str, Enum`，改用 `StrEnum`（UP042，ruff 强制）
- Import 排序：标准库 → 第三方 → 本地（I001，ruff 强制）

### 提交规范

遵循 Conventional Commits：
```
feat:  新功能
fix:   修复 bug
docs:  文档更新
refactor: 重构（无功能变化）
chore: 构建、依赖、配置
```

---

## 常见问题

**Q: `npm run lint` 报 ESLint 找不到 config**
A: 需要 `eslint.config.js`（flat config），已存在于 `frontend/`。若 node_modules 未安装，先 `npm install`。

**Q: `uv run ruff` 报 ruff 找不到**
A: 用 `uv tool run ruff`，或 `uv sync --extra dev` 后用 `.venv/bin/ruff`。

**Q: 前端 `import.meta.env` TS 报错**
A: `tsconfig.json` 需有 `"types": ["vite/client"]`，已配置。

**Q: 风险徽章颜色在深色背景下不可见**
A: 不要用 `diagnosisStore.riskLevelColor`，使用组件本地的 `darkRiskColors`。

**Q: SSE 流式输出中途中断**
A: 检查 `AbortController` 是否被意外触发；`useSSEDiagnosis.ts` 在每次 `run()` 前会调用 `abortRef.current?.abort()` 取消上一次请求。

**Q: 后端 Docker 容器启动超时 / 健康检查失败**
A: 首次启动需下载约 4GB 嵌入模型。挂载 `models_cache` 卷后重启秒级完成。详见 `docs/07-build-deploy.md` 第 9 节。

**Q: K8s SSE 流在 Ingress 处中断**
A: 确认 nginx Ingress 注解包含 `nginx.ingress.kubernetes.io/proxy-buffering: "off"` 和 `proxy-read-timeout: "300"`。详见 `scripts/k8s/06-ingress.yaml`。
