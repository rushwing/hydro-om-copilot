# LangSmith 可观测性集成：架构、配置与使用指南

## 1. 为什么需要 LLM 可观测性

### 1.1 传统 APM 的盲区

传统应用性能监控（Datadog, New Relic 等）追踪的是函数调用链路和 HTTP 响应时间，对 LLM 应用存在以下盲区：

| 盲区 | 说明 |
|------|------|
| Prompt 内容不可见 | 无法知道 LLM 实际收到了什么 prompt |
| Token 消耗不透明 | 无法按节点追踪 input/output token 数 |
| 推理链不可审计 | 无法回溯特定诊断结果的推理过程 |
| 模型输出质量 | 无法追踪 JSON 解析失败率、幻构字段率 |
| 检索质量 | 无法知道 RAG 命中了哪些文档 |

### 1.2 水电诊断场景的特殊需求

水电运维是**高责任场景**：每次诊断输出都可能影响实际操作决策。因此：

- **每次诊断的完整推理链必须可审计**：事后能回溯"为什么给出这个根因"
- **错误诊断需要快速定位**：是 retrieval 问题（召回错误文档）还是 reasoning 问题（LLM 推理错误）
- **知识库更新后需验证质量**：新增 L3 文档后，确认诊断质量提升而非下降

---

## 2. LangSmith 集成架构

### 2.1 集成方式

LangSmith 通过环境变量自动拦截所有 LangChain/LangGraph 调用，无需修改业务代码：

```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__xxxxxxxxxxxx
LANGCHAIN_PROJECT=hydro-om-copilot
```

设置后，所有经过 LangChain 的 LLM 调用、链调用、工具调用自动上传到 LangSmith。

配置来源：`backend/app/config.py:38-40`

```python
langchain_tracing_v2: bool = False
langchain_api_key: str = ""
langchain_project: str = "hydro-om-copilot"
```

### 2.2 Trace 层级

```
Project: hydro-om-copilot
└── Run (1 次诊断请求，session_id = xxx)
    ├── symptom_parser  [Node Span]
    │   └── ChatAnthropic  [LLM Span]
    │       ├── input:  SYMPTOM_PARSER_PROMPT + query
    │       ├── output: {"unit_id": ..., "symptoms": [...]}
    │       └── usage:  {input_tokens: 120, output_tokens: 85}
    ├── retrieval  [Node Span]
    │   ├── HybridRetriever.procedure  [Retrieval Span]
    │   ├── HybridRetriever.rule       [Retrieval Span]
    │   └── HybridRetriever.case       [Retrieval Span]
    ├── reasoning  [Node Span]
    │   └── ChatAnthropic  [LLM Span]
    │       ├── input:  REASONING_PROMPT + context
    │       ├── output: {"root_causes": [...], "risk_level": "high"}
    │       └── usage:  {input_tokens: 1800, output_tokens: 420}
    └── report_gen  [Node Span]
        └── ChatAnthropic  [LLM Span]
            ├── input:  REPORT_GEN_PROMPT + root_causes
            ├── output: {"check_steps": [...], "report_draft": "..."}
            └── usage:  {input_tokens: 600, output_tokens: 380}
```

### 2.3 与 LangGraph 的原生集成

LangGraph 每个节点（`symptom_parser`, `retrieval`, `reasoning`, `report_gen`）在 LangSmith 中自动成为独立 Span，携带：
- 节点名称和执行时间
- 输入 state（可选，通过 `langchain_verbose=True` 启用）
- 输出 state diff
- 子调用（LLM、工具）的完整链路

无需手工添加任何 tracing 代码。

---

## 3. 配置说明

### 3.1 `.env.example` 中的配置项

```bash
# LangSmith 可观测性（可选，本地开发可不填）
LANGCHAIN_TRACING_V2=false          # 本地开发：禁用
LANGCHAIN_API_KEY=                  # 生产：填入 LangSmith API Key
LANGCHAIN_PROJECT=hydro-om-copilot  # 项目名称（按电厂可自定义）
# LANGCHAIN_ENDPOINT=https://api.smith.langchain.com  # 默认值，私有化部署时修改
```

### 3.2 环境配置策略

> **央企数据边界要求**：水电厂运维数据（设备编号、运行参数、故障症状）属于生产安全敏感数据，可能受电力监管和企业数据分级制度约束。生产环境**默认禁用**外部 SaaS 追踪，仅在完成数据分级审批、明确数据出境合规路径后，方可选择性开启。

| 环境 | `LANGCHAIN_TRACING_V2` | 说明 |
|------|----------------------|------|
| 本地开发 | `false` | 无需 API Key，节省配置成本 |
| CI/CD | `false` | 测试运行不上传 trace |
| Staging | `true`（可选） | 验证 trace 完整性，使用脱敏测试数据，project 名加 `-staging` 后缀 |
| 生产 | **`false`（默认禁用）** | 默认关闭外部追踪；如需开启须通过数据分级审批，且必须配合 `LANGCHAIN_HIDE_INPUTS=true` 或改用自托管方案 |

**生产环境替代方案（按优先级排序）**：
1. **结构化本地日志**（推荐默认）：记录 `session_id`、`risk_level`、`sources`、各节点耗时，不含用户 query 和 HMI 截图。满足基本可观测性，零数据出境风险。
2. **自托管 LangSmith**（见第 6 节）：数据不离境，适合有 K8s 基础设施的电厂。
3. **LangSmith SaaS + 输入隐藏**：仅在完成数据合规审批后，配合 `LANGCHAIN_HIDE_INPUTS=true` 使用，仅保留 token 计数和延迟数据。

### 3.3 多电厂 Project 命名建议

```bash
# 电厂 A 生产
LANGCHAIN_PROJECT=hydro-om-yantan-prod

# 电厂 B 生产
LANGCHAIN_PROJECT=hydro-om-longtan-prod

# 通用测试
LANGCHAIN_PROJECT=hydro-om-copilot-dev
```

每个 Project 独立的好处：在 LangSmith UI 中可按电厂筛选 trace，便于分析不同电厂的诊断质量差异。

### 3.4 数据隐私处理建议

LangSmith 默认将完整 prompt（含用户 query）上传至 LangSmith 服务器（Anthropic/US-East 托管）。

水电运维场景的敏感字段：
- `raw_query`：运维人员描述的故障症状（可能含设备编号、运行参数）
- `image_base64`：HMI 截图（包含实时运行数据）

建议：
1. **生产环境**：使用 `LANGCHAIN_HIDE_INPUTS=true` 隐藏 LLM 输入（仅保留 token 计数和延迟）
2. **或使用自托管 LangSmith**（见第 6 节）
3. **最小化方案**：关闭 LangSmith，仅使用结构化日志记录 session_id、risk_level、sources（不含用户 query）

---

## 4. 可追踪指标

### 4.1 Token 消耗（按节点）

通过 LangSmith UI 可按节点查看每次诊断的 token 消耗：

| 节点 | 典型 input tokens | 典型 output tokens | 累计成本（预估） |
|------|-----------------|------------------|----------------|
| symptom_parser | ~120 | ~80 | $0.0003 |
| reasoning | ~1500-2000 | ~400-600 | $0.005-0.008 |
| report_gen | ~600-800 | ~350-500 | $0.002-0.004 |
| **总计** | | | **~$0.008-0.013/次** |

*注：基于 claude-sonnet-4-6 定价预估，实际以 Anthropic 官方定价为准。*

### 4.2 各节点耗时

LangSmith Trace 时间线视图显示每个 Span 的开始/结束时间，可识别：
- 哪个节点是瓶颈（通常是 reasoning）
- retrieval 的并行效果（3 路检索在 timeline 中并排显示）
- LLM TTFT（Span 开始到第一个 token 的时间）

### 4.3 RAG 检索命中文档追踪

`retrieval` 节点将 `sources`（doc_id 列表）写入 AgentState：

```python
# retrieval.py:41-43
sources = list(
    {doc["doc_id"] for doc in procedure_docs + rule_docs + case_docs if "doc_id" in doc}
)
```

这些 `sources` 在 LangSmith 的 Span 输出中可见，用于分析：
- 哪些文档被高频命中（可能需要内容优化）
- 哪些查询没有命中预期文档（retrieval 质量问题）
- 规则库命中率（`L2.SUPPORT.RULE.001` 是否总在 critical 场景中被召回）

### 4.4 错误率与失败节点定位

LangSmith 在 Trace 列表中标记失败的 Run（红色），点击可查看：
- 哪个节点抛出异常
- 完整的 error traceback
- 失败时的 input state（便于复现）

---

## 5. 评估（Evaluation）接入

### 5.1 LangSmith Dataset + Evaluator 基本使用

1. **创建 Dataset**：在 LangSmith UI 中上传黄金标准测试集（见 `03-rag-kb-design.md` 第 7 节）
2. **运行评估**：`client.evaluate(target_function, data=dataset, evaluators=[...])`
3. **查看结果**：LangSmith UI 中对比不同 prompt 版本的评估分数

### 5.2 为 3 类诊断场景创建 Golden Dataset

```json
[
  {
    "inputs": {"query": "1号机组推力轴承温度持续升高，冷却水流量正常"},
    "outputs": {
      "expected_root_causes": ["推力瓦面磨损", "油膜破裂"],
      "expected_risk_level": "high",
      "expected_sources_contains": ["L2.TOPIC.BEAR.001"]
    }
  },
  {
    "inputs": {"query": "调速器油压低，压油罐压力 2.8MPa（额定 3.2MPa）"},
    "outputs": {
      "expected_root_causes": ["补气阀故障", "漏油"],
      "expected_risk_level": "high",
      "expected_sources_contains": ["L2.TOPIC.GOV.001", "L2.SUPPORT.RULE.001"]
    }
  }
]
```

### 5.3 自定义 Evaluator：诊断根因匹配率

```python
def root_cause_match_evaluator(run, example):
    """检查 top-1 根因是否匹配专家标注"""
    predicted = run.outputs.get("root_causes", [{}])[0].get("title", "")
    expected_keywords = example.outputs.get("expected_root_cause_keywords", [])
    match = any(kw in predicted for kw in expected_keywords)
    return {"score": 1 if match else 0, "key": "root_cause_match"}
```

**注**：此 evaluator 需专家标注 golden dataset，目前为占位设计。建议在 L3 语料接入后，由厂站专家提供 10-20 个真实诊断案例作为标注基础。

---

## 6. 替代方案（私有化部署 / 数据不出境）

### 6.1 LangSmith 自托管版本

LangSmith Enterprise 支持在企业私有云部署，Trace 数据不上传至 LangSmith SaaS。

适用场景：电厂数据安全要求不允许上传至第三方云服务。

### 6.2 轻量替代：OpenTelemetry + Jaeger

```python
# 使用 opentelemetry-sdk 手工 instrument LangChain 调用
from opentelemetry import trace
tracer = trace.get_tracer("hydro-om-copilot")

with tracer.start_as_current_span("reasoning_node") as span:
    span.set_attribute("query", state["raw_query"])
    result = await reasoning_node(state)
    span.set_attribute("risk_level", result["risk_level"])
```

Jaeger UI 提供 Trace 时间线视图，数据存储在本地（Elasticsearch 或 Cassandra）。

代价：需自行实现 LangChain instrumentation，不如 LangSmith 开箱即用。

### 6.3 最小可行实现：结构化日志 + ELK

最低成本方案：在每次诊断完成后，输出结构化 JSON 日志：

```python
import structlog
log = structlog.get_logger()

log.info(
    "diagnosis_complete",
    session_id=state["session_id"],
    topic=state["topic"],
    risk_level=state["risk_level"],
    sources=state["sources"],
    # 不记录 raw_query 和 image_base64（隐私保护）
    node_durations={"symptom_parser": 1.8, "reasoning": 6.2, ...},
)
```

通过 Filebeat → Logstash → Elasticsearch → Kibana 形成可查询的日志分析平台，满足基本审计需求。

---

## 7. 后续集成路径（Roadmap）

### 7.1 在线 A/B 测试不同 Prompt 版本

LangSmith 支持同一 Dataset 对比两套 prompt 的评估分数：

```
prompt_v1: REASONING_PROMPT（当前版本）
prompt_v2: REASONING_PROMPT + "请优先考虑设备年龄和历次检修记录"（实验版本）
```

在 L3 台账接入后，通过 A/B 测试确认 prompt 改进带来的实际诊断质量提升。

### 7.2 用户反馈写回 LangSmith

前端"诊断结果"卡片底部添加 👍/👎 按钮，用户反馈通过 LangSmith feedback API 写回对应 Run：

```python
client.create_feedback(
    run_id=run_id,
    key="diagnosis_quality",
    score=1,  # 1=好, 0=差
    comment="根因判断准确，步骤清晰",
)
```

积累足够反馈后，可将高质量 Run 导出为 Golden Dataset 用于评估。

### 7.3 自动 Regression Testing

每次知识库更新（`ingest_kb.py` 运行）后，触发自动评估：

```bash
# CI/CD 钩子（占位）
python scripts/eval_retrieval.py --compare-baseline
# 若 Top-5 Recall 下降 > 5%，标记为失败，阻止知识库部署
```
