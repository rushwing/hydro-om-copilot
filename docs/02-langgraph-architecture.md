> **适用场景**：修改 LangGraph 节点、AgentState 字段、节点间路由逻辑时

# LangGraph 状态机架构设计、业务约束与能力边界

## 1. 设计动机：为什么用 StateGraph 而非直接调用链

### 1.1 节点隔离与错误边界

手工 async 调用链将所有逻辑串联在一个函数中，任何中间步骤的异常都会中断整条链路。LangGraph StateGraph 的每个节点是独立的 async 函数，输出写入 `AgentState` 的指定字段：

- `symptom_parser` 失败 → `state.error` 写入错误信息，后续节点可检查并降级处理
- `image_agent` 失败 → `state.ocr_text` 为 None，retrieval 节点仍可继续（仅使用文本查询）
- 节点函数可单独 mock `AgentState` 进行单元测试，无需运行整条链

### 1.2 每个节点输出 partial state

节点函数只返回它修改的字段（`dict`），LangGraph 自动 merge 到全局 `AgentState`：

```python
# symptom_parser_node 只返回它负责的字段
return {
    "parsed_symptom": result,
    "topic": topic,
}
# 不修改 raw_query、image_base64、retrieved 等其他字段
```

这种设计的好处：
- 节点职责单一，易于理解和测试
- 不同节点可并发执行（当无数据依赖时）
- 状态演化可追踪（LangSmith 按节点记录 state diff）

---

## 2. AgentState 字段设计

完整定义见：`backend/app/agents/state.py`

### 2.1 字段生命周期

| 字段 | 类型 | 生产节点 | 消费节点 | 说明 |
|------|------|----------|----------|------|
| `session_id` | `str` | API 层（UUID4） | — | 全生命周期不变 |
| `raw_query` | `str` | API 层 | symptom_parser, retrieval, reasoning | 用户原始输入，不可修改 |
| `image_base64` | `Optional[str]` | API 层 | route_after_parse, image_agent | base64 编码的截图 |
| `parsed_symptom` | `Optional[ParsedSymptom]` | symptom_parser | reasoning, report_gen | LLM 结构化解析结果 |
| `ocr_text` | `Optional[str]` | image_agent | retrieval, reasoning | HMI 截图 OCR 文本 |
| `topic` | `Optional[str]` | symptom_parser | retrieval | 故障类型路由键 |
| `retrieved` | `Optional[RetrievedContext]` | retrieval | reasoning | 三库检索结果 |
| `root_causes` | `list[dict]` | reasoning | report_gen | Top-3 根因假设 |
| `check_steps` | `list[dict]` | report_gen | API 层（输出） | 结构化检查步骤 |
| `risk_level` | `str` | reasoning | report_gen, API 层 | low/medium/high/critical |
| `escalation_required` | `bool` | reasoning | report_gen | 是否需要升级处理 |
| `escalation_reason` | `Optional[str]` | reasoning | report_gen | 升级原因说明 |
| `report_draft` | `Optional[str]` | report_gen | API 层（输出） | 班组交班汇报草稿 |
| `stream_tokens` | `Annotated[list[str], operator.add]` | 各 LLM 节点 | SSE streaming | token 流累积 |
| `sources` | `list[str]` | retrieval | API 层（输出） | 引用文档 doc_id 列表 |
| `error` | `Optional[str]` | 任意节点 | API 层 | 错误信息，不中断流程 |

### 2.2 `stream_tokens` 的 `operator.add` reducer 设计

`stream_tokens` 使用 `Annotated[list[str], operator.add]` 注解。`operator.add` 是 Python 内置的列表拼接函数，语义清晰：将新 token 列表追加到现有列表末尾。

```python
# 当节点返回 {"stream_tokens": ["新 token"]} 时
# LangGraph 调用 operator.add(current_list, ["新 token"])
# 等价于 current_list + ["新 token"]，结果是追加而非替换
```

**为何不用 `add_messages`**：`add_messages` 是 LangGraph 专为 `BaseMessage` 对象列表设计的 reducer，包含消息去重、ID 合并等消息对象特有逻辑，不适合用于纯字符串列表。对 `list[str]` 使用 `add_messages` 会导致类型语义不匹配，并在 LangGraph 升级或消息结构变化时有运行时异常风险。

SSE streaming 层（`streaming.py`）监听 `on_chat_model_stream` 事件直接推送 token，`stream_tokens` 主要用于 LangSmith trace 记录完整 token 序列。

---

## 3. 节点拓扑图与数据流

### 3.1 完整流程图

```
用户请求 (raw_query + image_base64?)
        │
        ▼
┌─────────────────┐
│  symptom_parser  │  LLM JSON 解析 → parsed_symptom, topic
└────────┬────────┘
         │
         ▼
   route_after_parse
    (条件边)
    ┌────┴────┐
    │         │
    │ image?  │ no image
    ▼         ▼
┌──────────┐ ┌───────────┐
│image_agent│ │           │
│ (OCR)    │ │           │
└────┬─────┘ │           │
     │       │           │
     └───────┼───────────┘
             ▼
     ┌───────────────┐
     │   retrieval   │  3路并行检索（asyncio.gather）
     │  ┌─────────┐  │  ├── procedure corpus
     │  │ BM25 +  │  │  ├── rule corpus
     │  │ Dense   │  │  └── case corpus
     │  │ + RRF   │  │
     │  └─────────┘  │
     └───────┬───────┘
             │
             ▼
     ┌───────────────┐
     │   reasoning   │  LLM → root_causes, risk_level, escalation
     └───────┬───────┘
             │
             ▼
     ┌───────────────┐
     │   report_gen  │  LLM → check_steps, report_draft
     └───────┬───────┘
             │
             ▼
            END
```

### 3.2 条件边 `route_after_parse`

```python
# backend/app/agents/graph.py:21-25
def route_after_parse(state: AgentState) -> str:
    if state.get("image_base64"):
        return "image_agent"
    return "retrieval"
```

判断逻辑：纯字符串检查 `image_base64` 字段是否非 None/非空。无需 LLM 判断，避免引入额外延迟和成本。

### 3.3 并行检索的 3 路 asyncio.gather

```python
# backend/app/agents/retrieval.py:33-38
procedure_task = asyncio.create_task(_retrieve("procedure", query, topic))
rule_task      = asyncio.create_task(_retrieve("rule", query, topic))
case_task      = asyncio.create_task(_retrieve("case", query, topic))

procedure_docs, rule_docs, case_docs = await asyncio.gather(
    procedure_task, rule_task, case_task
)
```

三路检索并发执行，总耗时取决于最慢的一路，而非三路串行之和（预估节省约 60-70% 检索时间）。

---

## 4. 主题路由设计

### 4.1 关键词打分逻辑

```python
# backend/app/agents/symptom_parser.py:25-40
TOPIC_KEYWORDS = {
    "vibration_swing":       ["振动", "摆度", "抖动", "晃动", "位移", "瓦振", "轴振"],
    "governor_oil_pressure": ["调速器", "油压", "压油罐", "主配压阀", "导叶", "开度", "漏油"],
    "bearing_temp_cooling":  ["轴承", "温度", "温升", "冷却水", "推力", "导轴承", "过热"],
}
```

评分：遍历 `parsed_symptom.symptoms + device`，统计各 topic 关键词命中次数，取最高分 topic。若全零分，默认 `vibration_swing`。

### 4.2 关键词 vs. LLM 分类的 Trade-off

| 维度 | 关键词打分（当前） | LLM Zero-shot 分类（未来） |
|------|------------------|--------------------------|
| 延迟 | < 1ms | +500-1000ms（额外 LLM 调用） |
| 成本 | 零 | 每次诊断增加 ~200 tokens |
| 准确率 | 专业词典覆盖范围内高 | 覆盖新故障类型能力强 |
| 可解释性 | 高（词命中可见） | 低（LLM 黑盒） |
| 升级条件 | 故障类型 > 10 类 / 召回率 < 80% | — |

### 4.3 TOPIC_KEYWORDS 的可扩展性

新增故障类型只需在 `TOPIC_KEYWORDS` 字典中添加一个 key，并在知识库中添加对应的 `L2.TOPIC.XXX.001` 文档，以及在 `_CORPUS_FILTER_MAP`（`hybrid_retriever.py:13-18`）中注册对应 doc_id。

---

## 5. 业务约束（硬性约束，不可逾越）

### 5.1 "辅助不替代"原则

系统定位为**辅助决策工具**，所有输出必须附带不确定性声明。`report_draft`（`prompts.py:REPORT_GEN_PROMPT`）生成的交班汇报草稿包含"初步判断"字样，明确为辅助意见而非最终结论。

**实现层面**：`DiagnosisResult` 模型中 `root_causes[].probability` 字段明确标注置信度，前端显示时附带"建议人工确认"提示。

### 5.2 规则库优先于 LLM 判断

`REASONING_PROMPT`（`prompts.py:65`）末尾指令：

> 严格按 JSON 输出，不要其他文字。**风险等级判断依据规则库中的超限阈值与操作红线。**

规则库（`L2.SUPPORT.RULE.001`）中的硬阈值（如"推力轴承温度 > 70°C 停机"）优先于 LLM 自由推理。即使 LLM 认为风险较低，只要规则库有明确红线，`risk_level` 必须升为 `critical`。

### 5.3 Critical 风险强制输出升级理由

`reasoning` 节点输出 `risk_level: "critical"` 时，`escalation_required` 必须为 `true`，`escalation_reason` 必须非空。前端检测到 critical 时显示强提示 UI（红色 badge 含 `critical-pulse` 闪烁动画，强制滚动到风险提示区域）。

### 5.4 不做自主控制指令

系统输出仅为**诊断建议和检查步骤**，不产生任何直接发送至 SCADA/DCS 的控制指令。`check_steps[].caution` 字段明确标注危险操作的人工确认要求（如"操作前确认调速器在手动模式"）。

Guardrails 层：
- 前端不提供"一键执行"按钮，只有"复制步骤"功能
- 后端无任何 SCADA 写入 API 接口

---

## 6. 当前能力边界（以现有语料为基准）

### 6.1 覆盖场景

| 故障类型 | topic 键 | 知识库覆盖 |
|----------|----------|-----------|
| 振动/摆度异常 | `vibration_swing` | L2.TOPIC.VIB.001 + L1 |
| 调速器/油压异常 | `governor_oil_pressure` | L2.TOPIC.GOV.001 + L1 |
| 轴承温度异常 | `bearing_temp_cooling` | L2.TOPIC.BEAR.001 + L1 |
| 通用运维知识 | 所有 topic | L1.ROUTER.001 + L1.OVERVIEW.001 |
| 规程规则 | 所有 topic | L2.SUPPORT.RULE.001 |
| 历史案例 | 所有 topic | L2.SUPPORT.CASE.001 |

### 6.2 当前不覆盖的场景

- **厂站特定保护定值**：L3 未接入，当前规则库为通用行业标准值
- **受限负荷区**：特定机组的振动敏感区需 L3 台账数据
- **历次缺陷记录**：设备历史维修记录需 L3 缺陷库
- **OCR 准确性**：不同 HMI 厂商（GE/ABB/国电南自）截图差异大，当前仅提取文本，不做结构化解析

### 6.3 OCR 能力限制

`image_agent` 节点调用 Claude vision API 进行文本提取，输出为 `ocr_text: str`（非结构化）。限制：
- 报警列表图片可能提取顺序错乱
- 曲线趋势图不做数值识别（仅描述趋势）
- 截图分辨率 < 800px 时准确率下降

---

## 7. L3 语料接入后的扩展能力边界

### 7.1 能力边界对比

| 能力 | L3 为空（当前） | L3 完整接入 |
|------|----------------|-------------|
| 根因置信度 | 通用知识，置信度 0.4-0.6 | 本厂台账 + 历史数据，置信度可达 0.7-0.85 |
| 阈值判断 | 行业通用标准（L2.SUPPORT.RULE） | 本厂保护定值（L3 专项定值库） |
| 案例相似度 | 行业公开案例 | 本厂历次缺陷库，相似度匹配精度更高 |
| 设备状态上下文 | 无 | 台账 → 设备年龄、上次检修时间、历史缺陷次数 |

### 7.2 各 L3 文档接入后的扩展路径

**接入 01_机组台账** → 根因置信度提升
- 台账中的设备参数（额定转速、轴承型号）补充 reasoning 节点的上下文
- 可判断"设备年龄超过大修周期"作为根因证据之一

**接入 03_保护定值** → 阈值判断从通用 → 本厂专家
- 替换 L2.SUPPORT.RULE.001 中的通用阈值
- `risk_level` 判断更准确，减少误报和漏报

**接入 05_历次缺陷** → 案例相似度检索维度新增
- 新增 `plant_<id>_case` collection，优先级高于通用案例库
- 相似案例检索的 RRF 融合权重可配置本厂案例优先

---

## 8. 未来架构扩展点

### 8.1 人机交互节点（Human-in-the-loop）

LangGraph 原生支持 `interrupt_before` / `interrupt_after` breakpoint：

```python
# 在 reasoning 之后暂停，等待专家确认根因假设
graph.compile(interrupt_after=["reasoning"])
```

实现路径：
1. SSE 推送 `status: {node: "reasoning", phase: "awaiting_human"}`
2. 前端显示"专家确认"UI，运维人员选择/修正根因
3. 前端 POST `/diagnosis/resume` 携带修正后的 state
4. LangGraph 从 breakpoint 恢复执行

### 8.2 多机组并发诊断

当前 `session_id` 由客户端生成（UUID4），`AgentState` 生命周期限于单次请求，天然支持多并发。扩展点：
- 跨 session 的机组状态关联（同一时刻多机组异常 → 可能是公共设备故障）
- 需要引入 Redis 作为跨 session 状态存储

### 8.3 Tool Calling 扩展（实时 SCADA 数据）

LangGraph 支持 Tool Node，可在 reasoning 节点中调用实时数据查询工具：

```python
@tool
async def query_scada(tag: str, time_range: str) -> dict:
    """查询 SCADA 实时/历史数据"""
    ...
```

约束：SCADA 连接为只读，不写入控制指令（符合 5.4 节业务约束）。
