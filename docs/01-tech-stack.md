> **适用场景**：技术选型 / trade-off 讨论、Lint 工具链配置、scale-up 架构规划时

# 技术选型逻辑、Scale-Up 可行性与 Trade-off

## 1. 选型全景表

| 层级 | 选型 | 备选方案 | 核心理由 |
|------|------|----------|----------|
| 前端框架 | React 18 | Vue 3, Svelte | 生态成熟，团队熟悉，LangChain.js 集成 |
| 构建工具 | Vite | CRA, webpack | 原生 ESM HMR < 100ms，冷启动 10x 快于 CRA |
| 类型系统 | TypeScript | JavaScript | Agent 输出结构复杂，强类型防止 SSE 解析错误 |
| CSS 框架 | Tailwind CSS v3 | styled-components, MUI | v4 仍 beta，shadcn/ui 不支持；v3 生产稳定 |
| 字体 | Rajdhani + Noto Sans SC + JetBrains Mono | Inter（已弃用） | 工业 HMI 视觉语言；中文可读性；等宽报告输出 |
| 前端 Lint | ESLint v9 + typescript-eslint | tslint（已停维护） | 原生 TS 类型感知 lint，flat config（`eslint.config.js`）|
| 状态管理 | Zustand | Redux, Jotai | 轻量级，SSE appendToken 场景下 selector 粒度精准 |
| 后端框架 | FastAPI | Django, Flask | 原生 async，StreamingResponse 天然支持 SSE |
| Agent 编排 | LangGraph | 手工 async 链, LangChain LCEL | StateGraph + 条件边 + 断点恢复，节点可单独测试 |
| 包管理 | uv | pip, poetry | Rust 实现，安装速度约 10x，lock file 可重现 |
| 后端 Lint | ruff | flake8 + isort + pyupgrade | 单工具覆盖格式化/排序/升级，速度快 10-100x |
| LLM | claude-sonnet-4-6 | GPT-4o, Gemini 1.5 Pro | 中文推理、结构化 JSON 输出质量最优 |
| 向量存储（dev） | ChromaDB | FAISS, Weaviate | 零配置本地运行，SQLite 持久化 |
| 向量存储（prod） | Qdrant | Pinecone, Weaviate | 开源可自托管，混合检索，分布式扩展 |
| 嵌入模型 | BAAI/bge-large-zh-v1.5 | text-embedding-3, m3e-base | 中文专业术语 embedding 质量最优，本地无 API 成本 |
| 重排序 | BAAI/bge-reranker-v2-m3 | cross-encoder/ms-marco | 同家族模型，与 bge 嵌入协同效果好 |
| 稀疏检索 | BM25 + jieba | ElasticSearch BM25 | 轻量，无需外部服务，与 RRF 融合简单 |
| 可观测性 | LangSmith | OpenTelemetry + Jaeger | 原生 LangGraph 集成，prompt 链路可视化 |

---

## 2. 前端栈

### 2.1 Vite 替代 CRA

- **HMR**：Vite 利用原生 ESM，模块热更新延迟 < 100ms；CRA 基于 webpack bundle，大项目 HMR 可达 5-30s
- **冷启动**：Vite 按需编译，首次启动仅编译入口模块；CRA 全量打包，冷启动随项目体积线性增长
- **Bundle size**：Vite rollup 输出支持 code splitting + tree shaking，典型生产包比 CRA 小 30-40%

### 2.2 TypeScript 的必要性

Agent 输出结构复杂（`DiagnosisResult` 含嵌套 `RootCause[]`、`CheckStep[]`、`RiskLevel` 枚举），SSE 流式解析时任何字段拼写错误都会导致静默 `undefined`。TypeScript 在编译期捕获这类错误，避免运行时诊断结果渲染异常。

关键类型文件：`frontend/src/types/diagnosis.ts`

### 2.3 Tailwind v3 而非 v4

- Tailwind v4 截至本项目搭建时仍为 beta，API 未稳定
- shadcn/ui 组件库明确依赖 v3，v4 存在兼容性断裂
- v3 的 JIT 编译模式已足够满足性能需求

### 2.4 Zustand 而非 Redux

| 维度 | Zustand | Redux Toolkit |
|------|---------|---------------|
| 包体积 | ~2KB | ~20KB |
| 样板代码 | 最小（create + set） | action/reducer/selector 三层 |
| SSE 实时更新 | `appendToken` 直接 `set(state => ...)` | 需要 dispatch action |
| selector 粒度 | 函数式，按需订阅 | `useSelector` 同样精准但更冗长 |
| DevTools | 支持（zustand/middleware） | 原生支持 |

`appendToken` 在 SSE 高频更新（每 token 一次）场景下，Zustand 的函数式 `set` 不触发无关组件重渲染。

---

## 3. 后端栈

### 3.1 FastAPI 与 SSE 的天然适配

FastAPI 基于 Starlette 的 ASGI 异步模型，`StreamingResponse` 接受 `AsyncGenerator[str]`，与 LangGraph 的 `astream_events` 直接组合。每个连接占用一个协程而非线程，支持大量并发 SSE 连接。

配置参数（`config.py`）：
- `api_host: 0.0.0.0`
- `api_port: 8000`
- `api_reload: bool`（开发时热重载）

### 3.2 LangGraph 相比手工 async 编排的优势

| 维度 | 手工 async 链 | LangGraph StateGraph |
|------|--------------|----------------------|
| 节点隔离 | 函数调用，共享局部变量 | 每个节点输入/输出 partial state，边界清晰 |
| 错误边界 | 需手工 try/except | 节点异常写入 `state.error`，不影响其他节点 |
| 条件路由 | if/else 混在业务逻辑中 | `add_conditional_edges` 声明式定义 |
| 可测试性 | 依赖整个调用链 | 每个节点函数可单独 mock state 测试 |
| 断点恢复 | 不支持 | `interrupt_before` / `interrupt_after` |
| 流式事件 | 需手工实现事件总线 | `astream_events` 原生支持 |

### 3.3 uv 的 10x 安装速度

uv 使用 Rust 实现，通过并行下载和增量缓存，典型 `uv sync` 耗时 < 5s（vs. `pip install -r requirements.txt` 的 60-120s）。在 CI/CD 中，每次构建节省约 1-2 分钟，对于需要频繁更新知识库依赖的场景尤为显著。

---

## 4. LLM：claude-sonnet-4-6

### 4.1 与竞品比较

| 维度 | claude-sonnet-4-6 | GPT-4o | Gemini 1.5 Pro |
|------|-------------------|--------|----------------|
| 中文专业术语推理 | 优秀 | 良好 | 良好 |
| 结构化 JSON 输出稳定性 | 高（少幻构字段） | 中（偶有额外字段） | 中 |
| 上下文窗口 | 200K tokens | 128K tokens | 1M tokens |
| 成本（输入/MTok） | 中 | 中 | 低 |
| 工具调用 / Function calling | 原生支持 | 原生支持 | 原生支持 |

水电诊断场景对 JSON 输出结构稳定性要求极高（`root_causes[].probability` 等字段若幻构会导致 Pydantic 解析失败），claude-sonnet-4-6 在此维度表现最优。

### 4.2 Temperature=0.1 的设计依据

诊断场景需要**确定性推理**而非创造性输出。低 temperature 确保：
- 相同症状输入 → 相同根因排序（可审计）
- 结构化 JSON 字段名不产生随机变体
- 概率值（`probability`）保持稳定，不因采样噪声跳变

来源：`backend/app/config.py:16` - `llm_temperature: float = 0.1`

### 4.3 Fallback 策略（P2 占位）

通过 `config.py` 的 `llm_model` 字段配置化切换，无需修改业务代码：

```
llm_model = "claude-sonnet-4-6"   # 默认
llm_model = "claude-haiku-4-5-20251001"  # 成本降级
llm_model = "gpt-4o"              # 供应商故障切换（需替换 ChatAnthropic → ChatOpenAI）
```

---

## 5. 向量存储迁移路径：ChromaDB → Qdrant

### 5.1 ChromaDB 的局限性

ChromaDB 使用 SQLite 作为持久化存储，`chroma_persist_dir = "./knowledge_base/vector_store"`：
- 单文件 SQLite，无法多进程写入（dev 环境可接受）
- 不支持分布式部署
- 过滤能力有限（基于 metadata `where` 查询）
- Collection 数量增大时（多电厂场景）性能下降

### 5.2 Qdrant 的生产能力

| 能力 | ChromaDB | Qdrant |
|------|----------|--------|
| 分布式 | 否 | 是（sharding + replication） |
| 混合检索 | 否 | 原生 sparse + dense |
| 过滤精度 | metadata WHERE | 强类型 payload filter |
| gRPC 接口 | 否 | 是（低延迟） |
| 快照/备份 | 否 | 是 |

### 5.3 迁移方案

切换仅需修改 `config.py`：
```
vector_store_type = "qdrant"
qdrant_url = "http://qdrant-service:6333"
```

`backend/app/rag/vectorstore.py` 的 `build_vectorstore()` 根据 `vector_store_type` 分支初始化不同客户端，业务代码零改动。

---

## 6. Scale-Up 可行性分析

### 6.1 水平扩展

```
负载均衡器 (Nginx / ALB)
    ├── FastAPI Worker × N  (uvicorn workers 或 Kubernetes Pod)
    ├── Qdrant Cluster       (3 节点，collection sharding)
    └── CDN (CloudFront)     (前端静态资源)
```

FastAPI 无状态（`AgentState` 生命周期限于单次请求），可直接水平扩展。Session ID 由客户端生成（UUID4），无需 sticky session。

### 6.2 多电厂支持：命名空间隔离

Collection 命名规范：`plant_<plant_id>_<corpus>`

例：
- `plant_yantan_procedure`
- `plant_yantan_rule`
- `plant_longtan_procedure`

隔离效果：
- 查询时通过 `plant_id` 路由到对应 collection，防止跨厂站语料污染
- 每个电厂可独立更新知识库，不影响其他电厂
- BM25 index 文件：`bm25_<plant_id>_<corpus>.pkl`

### 6.3 多模态扩展：HMI 截图 → 视频帧

当前能力：单张 HMI 截图 → OCR 文本提取（`image_agent` 节点）

路径预留：
1. 视频帧：`image_agent` 接受 `frames: list[str]` 并行处理多帧，OCR 结果 concat
2. 时序数据：`image_agent` 调用 Claude vision API 分析曲线趋势图
3. 边界：不做实时摄像头流分析（单次诊断请求范式）

### 6.4 多语言 LLM 支持

通过 `config.py:llm_model` 运行时切换，prompts.py 中所有提示词保持中文（目标用户为中文运维人员）。若需多语言支持，prompts.py 按语言分目录即可。

---

## 7. Lint 工具链

### 7.1 前端：ESLint v9 + typescript-eslint

ESLint v9 迁移至 flat config（`eslint.config.js`），移除了 `.eslintrc.*` 格式。配置入口：

```js
// frontend/eslint.config.js
import tseslint from "typescript-eslint";

export default tseslint.config(
  ...tseslint.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx}"],
    rules: {
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/no-unused-expressions": ["error", { allowShortCircuit: true }],
    },
  },
  { ignores: ["dist/**", "node_modules/**"] },
);
```

`allowShortCircuit: true` 用于兼容 `useSSEDiagnosis.ts` 中的 `condition && fn()` 短路调用模式（该文件不可修改）。

执行：`npm run lint`（`cd frontend` 后）

### 7.2 后端：ruff

`pyproject.toml` 中配置：
```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]
```

规则集含义：
- `E` — pycodestyle 格式错误
- `F` — Pyflakes（未使用 import、未定义名称）
- `I` — isort 排序
- `UP` — pyupgrade（Python 3.11 语法升级，如 `Optional[X]` → `X | None`，`StrEnum`）

执行：`uv tool run ruff check backend/`（项目根目录）
自动修复：`uv tool run ruff check --fix backend/`

---

## 8. 已知 Trade-off 汇总

| Trade-off | 当前选择 | 代价 | 触发升级条件 |
|-----------|----------|------|--------------|
| ChromaDB vs Qdrant | ChromaDB（dev） | 无法多进程写入 | 生产部署 / 多电厂 |
| BM25 Pickle vs ES | Pickle 文件 | 无法增量更新，重建成本 O(n) | 文档量 > 10K / 在线更新需求 |
| ~~双调用模式~~ (**已废弃**) | ~~astream + ainvoke~~ → 单次 astream_events + on_chain_end 累积 | 双调用：LLM 成本翻倍、延迟翻倍、结果不一致风险 | 已修复，禁止在生产路径中使用 |
| 关键词路由 vs LLM 分类 | 关键词打分 | 不覆盖新故障类型 | 故障类型 > 10 类 / 召回率 < 80% |
| 本地嵌入 vs API 嵌入 | 本地 BGE | 首次加载 ~2GB 模型权重 | GPU 推理加速需求 / 云端部署 |
| SSE vs WebSocket | SSE | 单向推送，无法客户端 → 服务端流 | 需要人机交互节点（human-in-the-loop） |
