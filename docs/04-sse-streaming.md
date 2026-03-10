# SSE 流式诊断设计、全链路考量与性能量化

## 1. 为什么需要流式输出

### 1.1 LangGraph 5 节点推理链的典型耗时

| 节点 | 耗时来源 | 预估耗时（P50） |
|------|---------|----------------|
| `symptom_parser` | LLM JSON 解析（~300 tokens） | 1.5-2.5s |
| `image_agent`（可选）| Claude vision OCR | 2-4s |
| `retrieval` | 3 路并行 BM25 + Dense 检索 | 0.5-1.5s |
| `reasoning` | LLM 根因推理（~800 tokens 输出） | 4-8s |
| `report_gen` | LLM 步骤生成（~500 tokens 输出） | 3-6s |
| **总计（无图片）** | | **9-18s** |
| **总计（含图片）** | | **11-22s** |

*注：以上为预估值，基于 claude-sonnet-4-6 API 延迟经验值，实际受网络条件影响。*

### 1.2 无流式方案的用户体验问题

无流式（`await graph.ainvoke()`）：
- 用户提交查询后看到空白页面或 loading spinner
- 等待 9-18 秒无任何反馈
- 用户无法判断系统是否在工作，倾向于重复提交或放弃
- 水电运维场景下，运维人员在紧急故障时等待超过 5 秒会显著降低信任感

### 1.3 有流式方案的用户体验提升

SSE 流式输出：
- 首字节（第一个 `status` 事件）< 800ms（symptom_parser 节点启动）
- 节点进度实时可见（"正在分析症状..." → "正在检索知识库..." → "正在推理根因..."）
- reasoning/report_gen 节点的 LLM token 实时显示，用户看到诊断内容逐字生成
- 感知等待时间减少约 60-70%（业界流式 UX 研究结论）

---

## 2. 技术选型：SSE vs. WebSocket vs. Long-polling

| 维度 | SSE | WebSocket | Long-polling |
|------|-----|-----------|--------------|
| 协议 | HTTP/1.1, HTTP/2 | ws:// (升级协议) | HTTP/1.1 |
| 方向 | 单向（服务端→客户端） | 双向 | 单向（响应式） |
| 断线重连 | 浏览器原生自动重连 | 需手工实现 | 需手工实现 |
| 浏览器原生支持 | `EventSource` API | `WebSocket` API | `fetch` |
| HTTP 中间件兼容性 | 高（Nginx/CDN 原生支持） | 需配置 Upgrade 头 | 高 |
| 实现复杂度 | 低 | 中 | 中 |
| HTTP/2 多路复用 | 支持（不占用额外连接） | 不适用 | 支持 |
| POST body 支持 | 需用 fetch（非 EventSource） | 握手后发送 | 支持 |

**选择 SSE 的核心理由：**

1. **单向推送足够**：诊断请求是"提交 → 等待结果"模式，无需客户端在流式过程中向服务端发送数据
2. **HTTP 兼容性好**：Nginx、AWS ALB、Cloudflare 等中间件对 SSE 有原生支持，仅需配置 `proxy_buffering off`
3. **FastAPI 原生支持**：`StreamingResponse(media_type="text/event-stream")` 即可，无需额外库
4. **断线重连**：浏览器 `EventSource` 原生支持自动重连（本项目使用 `fetch` 实现，手动处理 abort）

---

## 3. 全链路 SSE 架构

### 3.1 端到端数据流

```
LangGraph.astream_events(state)
        │
        │  on_chain_start/end → {"node": "symptom_parser", "phase": "start"}
        │  on_chat_model_stream → {"text": "推力轴承..."}
        ▼
streaming.py:stream_agent_events()
  [AsyncIterator[str]]
        │
        │  "event: status\ndata: {...}\n\n"
        │  "event: token\ndata: {...}\n\n"
        ▼
diagnosis.py:event_generator()
  [AsyncGenerator]
        │
        │  (streaming 完成后)
        │  → graph.ainvoke(state)    ← 双调用（获取最终结构化结果）
        │  "event: result\ndata: {...}\n\n"
        ▼
FastAPI StreamingResponse
  [text/event-stream]
        │
        │  HTTP chunked transfer encoding
        ▼
浏览器 fetch + ReadableStream
  (diagnosisApi.ts:streamDiagnosis)
        │
        │  buffer 拼接 + SSE 解析
        │  onStatus() / onToken() / onResult() / onError()
        ▼
useDiagnosisStore (Zustand)
  │  setPhase(node)
  │  appendToken(text)   ← streamText += text
  │  setResult(result)
        ▼
React 组件（DiagnosisPanel）
  实时渲染 streamText + phase 进度条
```

### 3.2 4 种事件类型设计意图

| 事件类型 | 数据格式 | 触发时机 | 前端处理 |
|----------|---------|---------|---------|
| `status` | `{"node": "reasoning", "phase": "start"}` | 每个节点开始/结束 | 更新 `phase`，显示进度指示器 |
| `token` | `{"text": "推力轴承..."}` | LLM 每个 token 输出 | `appendToken(text)`，实时显示流式文字 |
| `result` | `DiagnosisResult` 完整 JSON | 所有节点执行完毕后 | `setResult(result)`，渲染结构化诊断卡 |
| `error` | `{"message": "..."}` | 任意节点异常 | `setError(message)`，显示错误提示 |

### 3.3 SSE 消息格式规范

```
event: status
data: {"node": "symptom_parser", "phase": "start"}

event: token
data: {"text": "根据症状分析，"}

event: result
data: {"session_id": "...", "root_causes": [...], "risk_level": "high", ...}

event: error
data: {"message": "symptom_parser failed: ..."}
```

规范：每条消息以 `\n\n` 结尾，`event:` 和 `data:` 字段各占一行，值为 UTF-8 JSON 字符串（`ensure_ascii=False`）。

实现参考：`backend/app/utils/streaming.py:9-12`

---

## 4. 最终 State 获取策略

### 4.1 问题背景

LangGraph 的 `astream_events` 是**流式执行事件流**，它逐步触发节点执行的事件（`on_chain_start`, `on_chat_model_stream` 等），但**不直接返回最终 `AgentState`**。

流式阶段只能获取 token 片段，无法直接获取 `root_causes`, `check_steps`, `risk_level` 等结构化字段。

### 4.2 推荐主方案：单次执行 + `on_chain_end` 捕获

在同一次 `astream_events` 中监听 `on_chain_end` 事件，从最后一个节点（`report_gen`）的输出直接提取完整 state：

```python
async def event_generator():
    final_output: dict = {}

    async for event in graph.astream_events(initial_state, version="v2"):
        kind = event["event"]
        name = event.get("name", "")

        if kind == "on_chain_start":
            yield sse_format("status", {"node": name, "phase": "start"})

        elif kind == "on_chat_model_stream":
            token = event["data"]["chunk"].content
            yield sse_format("token", {"text": token})

        elif kind == "on_chain_end" and name == "report_gen":
            # v2 事件的 on_chain_end 包含节点输出 dict
            output = event.get("data", {}).get("output", {})
            final_output = output  # 直接使用，无需二次 ainvoke

    if final_output:
        result = DiagnosisResult(**_extract_result_fields(final_output))
        yield sse_format("result", result.model_dump())
```

**优点**：单次执行，LLM 节点只调用一次，流式文本与结构化结果来自同一次推理，逻辑一致。

**前提**：需验证目标 LangGraph 版本的 `astream_events version="v2"` 在 `on_chain_end` 中确实返回完整 output dict（已在 LangGraph ≥ 0.2.0 中支持）。

### 4.3 ⚠ 已知缺陷实现（禁止作为生产默认方案）

> **警告**：以下"双调用"模式存在架构级缺陷，**不得在生产环境作为默认方案**。仅在调试或验证 `on_chain_end` 输出格式时作为临时手段使用。

```python
# ⚠ 调试专用 — 禁止用于生产
async def event_generator_debug():
    # 第一次调用：流式推送 token 和 status 事件
    async for chunk in stream_agent_events(graph, initial_state):
        yield chunk

    # 第二次调用：重复执行整个 graph（所有 LLM 节点重复计费！）
    final_state = await graph.ainvoke(initial_state)
    result = DiagnosisResult(...)
    yield sse_format("result", result.model_dump())
```

**代价分析**（架构级缺陷，不只是性能问题）：

| 缺陷项 | 说明 |
|--------|------|
| LLM 调用翻倍 | reasoning + report_gen 各执行 2 次，每次诊断成本约 2× |
| 延迟翻倍 | ainvoke 串行在 astream_events 之后，总耗时 ≈ 2 倍推理时间 |
| 结果不一致风险 | 两次推理为独立随机过程（temperature > 0），流式文本与结构化结果可能来自不同推理，存在矛盾 |
| 可解释性丧失 | 用户看到的流式推理与最终输出的根因不对应 |

---

## 5. 响应头设计

实现参考：`backend/app/api/routes/diagnosis.py:78-86`

```python
return StreamingResponse(
    event_generator(),
    media_type="text/event-stream",
    headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    },
)
```

| 响应头 | 值 | 作用 |
|--------|-----|------|
| `Cache-Control` | `no-cache` | 禁止浏览器和中间代理缓存 SSE 响应 |
| `X-Accel-Buffering` | `no` | 禁用 Nginx `proxy_buffering`（关键！否则 Nginx 会缓冲响应直到连接关闭） |
| `Connection` | `keep-alive` | 维持长连接，防止中间代理超时断开 |

**注意**：Nginx 配置还需在 `location` 块中设置：
```nginx
proxy_buffering off;
proxy_cache off;
proxy_read_timeout 300s;
```

---

## 6. 前端消费设计

### 6.1 选择 `fetch + ReadableStream` 而非 `EventSource` API

| 维度 | EventSource | fetch + ReadableStream |
|------|-------------|----------------------|
| HTTP 方法 | 仅 GET | GET/POST（本项目需要 POST body） |
| 自定义请求头 | 不支持 | 支持（Bearer token 等） |
| 请求体 | 不支持 | 支持（`DiagnosisRequest` JSON） |
| AbortController | 不原生支持 | 原生支持 |
| 浏览器兼容性 | IE 不支持（不影响本项目） | 现代浏览器全支持 |

本项目诊断请求需要 POST body（`query`, `image_base64`, `session_id`），因此必须使用 `fetch`。

### 6.2 Buffer 拼接处理（粘包/分包）

SSE 消息可能跨 chunk 边界（TCP 分包）或一个 chunk 中包含多条消息（粘包）。前端需要维护 buffer：

```typescript
// diagnosisApi.ts（示意，实际实现见源码）
let buffer = "";

reader.read() → chunk
buffer += chunk
const parts = buffer.split("\n\n")
buffer = parts.pop()  // 最后一个可能不完整，留存 buffer
for (const part of parts) {
    parseSSEMessage(part)  // event: xxx / data: xxx
}
```

### 6.3 AbortController 的 cancel 机制

```typescript
// useSSEDiagnosis.ts:13-21
const abortRef = useRef<AbortController | null>(null);

const run = useCallback(async (request) => {
    abortRef.current?.abort();  // 取消上一次请求
    abortRef.current = new AbortController();
    // ...
    await streamDiagnosis(request, handlers, abortRef.current.signal);
}, [...]);

const abort = useCallback(() => {
    abortRef.current?.abort();
    setPhase("idle");
}, [setPhase]);
```

用户切换页面或主动取消时，`AbortController.abort()` 触发 `fetch` 中止，服务端的 `StreamingResponse` generator 在下次 `yield` 时感知到客户端断开并退出。

### 6.4 Zustand `appendToken` 实时渲染

```typescript
// diagnosisStore.ts:42-44
appendToken: (text) =>
    set((state) => ({ streamText: state.streamText + text })),
```

`appendToken` 在每个 token 事件时调用，`streamText` 字段累积所有 token。React 组件通过 `useDiagnosisStore(s => s.streamText)` 订阅，仅当 `streamText` 变化时重渲染该组件，不触发其他组件更新。

---

## 7. 性能量化指标

### 7.1 基线：无流式方案延迟

| 指标 | 预估值（无图片） | 预估值（含图片） |
|------|----------------|----------------|
| P50 端到端延迟 | 9-12s | 12-18s |
| P95 端到端延迟 | 15-20s | 20-28s |
| 用户等待感知 | 全程白屏/spinner | 全程白屏/spinner |

*注：预估值，实际受 API 负载和网络延迟影响。*

### 7.2 流式方案目标指标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| TTFT（Time To First Token）| < 800ms | 从提交到第一个 `status` 事件 |
| 首个 LLM token 可见 | < 3s | symptom_parser 完成 + reasoning 开始 |
| 感知等待时间减少 | ~60-70% | 业界流式 UX 标准（Shneiderman 响应时间法则） |
| SSE 事件频率 | 10-50 events/s | reasoning 节点 token 流密集期 |

### 7.3 Token 吞吐

claude-sonnet-4-6 典型输出速度：约 60-80 tokens/s（预估，受服务器负载影响）。

reasoning 节点输出约 400-600 tokens（根因 + 风险判断），流式持续时间约 5-10s，用户体验为"看到诊断内容逐渐生成"。

### 7.4 SSE 带宽开销

| 事件类型 | 典型大小 | 每次诊断数量 | 总计 |
|----------|---------|-------------|------|
| `status` | ~80 bytes | ~10 | ~800 bytes |
| `token` | ~50 bytes | ~500-800 | ~25-40 KB |
| `result` | ~2-5 KB | 1 | ~2-5 KB |
| **总计** | | | **~28-46 KB** |

每次诊断 SSE 流量约 30-50 KB，相比诊断本身的价值可完全忽略。

---

## 8. 已知限制与 P2 优化方向

### 8.1 HTTP/1.1 连接限制

HTTP/1.1 下，每个 SSE 连接占用一个持久 TCP socket。浏览器对同一域名的并发连接数限制为 6（HTTP/1.1 规范）。

影响：用户同时开启多个诊断标签页时，超过 6 个并发 SSE 连接会被队列化。

缓解：升级到 HTTP/2（Nginx `http2` 配置），SSE 通过多路复用不占用额外连接。

### 8.2 Nginx 代理缓冲配置

生产部署时必须在 Nginx 中关闭代理缓冲，否则 SSE 消息会在 Nginx buffer 中积累，导致"批量发送"效果（失去流式体验）：

```nginx
location /api/diagnosis/ {
    proxy_pass http://backend:8000;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 300s;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
}
```

### 8.3 双调用问题的根因与修复方案

**根因**：LangGraph `astream_events` API 设计为事件流，不返回 state 快照。`ainvoke` 是唯一能获取最终完整 state 的同步接口。

**修复方案（P2）**：
1. 在 `astream_events` 的 `on_chain_end` 事件中，当 `name == "report_gen"` 时，尝试从 `event["data"]["output"]` 提取最终 state（需验证 LangGraph API 支持）
2. 或在 `report_gen` 节点内部将最终结果写入 `stream_tokens`，`stream_agent_events` 在接收到特殊标记 token 时解析完整 state

**当前接受双调用代价的理由**：诊断结果的正确性优先于 API 调用效率；P2 优化在确认 LangGraph API 行为后进行。
