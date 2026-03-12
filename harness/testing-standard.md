---
harness_id: TEST-001
component: testing / verification
owner: Engineering
version: 0.1
status: draft
last_reviewed: 2026-03-12
---

# Harness Standard — 测试与验证规程

> 本规范定义 Hydro O&M Copilot 在 Harness Engineering 范式下的测试分层、
> mock 策略、真实 LLM 使用边界、运行门禁与验收口径。
> 目标是让测试结果可复现、成本可控、失败原因可定位。

---

## 1. 适用范围

- **组件**：前端应用、后端 API、自动诊断服务、SSE 流、RAG 检索链路、LLM 调用封装
- **输入类型**：代码、配置、测试夹具、mock 数据、E2E 场景、canary prompt
- **触发时机**：
  - [ ] 新增测试框架、测试目录或运行脚本时
  - [ ] 新增外部依赖（LLM / 向量库 / 浏览器自动化）时
  - [ ] 修改 PR / CI / nightly 测试门禁时
  - [ ] 新增需要真实 LLM 成本预算的测试时

---

## 2. 测试分层规范

> 默认遵循“越靠近 PR 越便宜、越稳定；越靠近真实 LLM 越少量、越受控”。

### 2.1 单元测试（Unit）

| 项目 | 内容 |
|---|---|
| 规则 | 单元测试必须隔离外部网络、真实 LLM、真实向量检索副作用 |
| 目标 | 验证纯函数、状态变更、边界分支、错误处理 |
| 典型范围 | `autoStore`、`ChecklistPanel`、`session_log`、`config`、`chunker`、`AutoDiagnosisService` 内部行为 |
| 默认数据源 | fixture / stub / fake clock / localStorage mock |
| 坏示例 | 单元测试里直接调用 Anthropic API 或真实知识库服务 |

### 2.2 集成测试（Integration）

| 项目 | 内容 |
|---|---|
| 规则 | **纯后端集成，不含浏览器**；允许真实启动 FastAPI，但默认 mock LLM 和嵌入模型 |
| 目标 | 验证 API 契约：SSE 事件顺序、队列语义、幂等性、异常分支、资源清理 |
| 典型范围 | `/diagnosis/run` 事件流契约、`/diagnosis/auto/*` 契约、stop/start/reset-cooldowns |
| stub 机制 | `app.dependency_overrides[get_graph]` + `patch retriever`（详见 §11.4、§11.6） |
| 默认数据源 | httpx AsyncClient + 固定 JSON fixture（`backend/tests/fixtures/`） |
| 坏示例 | 集成测试含浏览器；依赖实时外网；未 patch 嵌入模型导致加载 4GB |

**失败归因边界**：Layer 2 失败 → API 契约或后端逻辑问题，与前端无关。

### 2.3 浏览器端到端测试（E2E）

| 项目 | 内容 |
|---|---|
| 规则 | E2E 关注真实用户流程，不负责验证模型文案本身；默认禁止真实 LLM |
| 目标 | 验证路由、表单、SSE 展示、历史归档、pending/completed 流转 |
| 推荐工具 | Playwright |
| SSE mock 方式 | `page.route('/diagnosis/run', handler)` 原生拦截，返回 `backend/tests/fixtures/sse/` 固定文本 |
| 典型范围 | 手动诊断提交、自动诊断查看、历史页归档、错误态展示 |
| 坏示例 | 引入 MSW；用 E2E 覆盖所有后端分支；E2E 依赖真实后端启动 |

**失败归因边界**：Layer 3 失败 → 前端渲染、路由或状态流转问题，API 契约已由 Layer 2 保证。

### 2.4 真实 LLM Canary

| 项目 | 内容 |
|---|---|
| 规则 | 真实 LLM 测试不得进入默认 PR / CI；仅允许手动触发或定时运行 |
| 目标 | 监控模型回归、prompt 漂移、结果结构稳定性 |
| 典型范围 | 少量固定 prompt 的结构化输出抽检 |
| 成本约束 | 必须设置最大样本数、最大 token 预算、失败通知口径 |
| 坏示例 | 每次 push 都跑真实 Anthropic 诊断链路 |

---

## 3. Mock 与真实依赖边界

### 3.1 默认必须 Mock 的依赖

- [ ] Anthropic / 其他 LLM API
- [ ] 外部网络请求
- [ ] 非确定性时间与随机数（如会影响断言）
- [ ] 真实付费向量检索或远端知识库服务

### 3.2 默认允许真实运行的依赖

- [ ] FastAPI 本地应用
- [ ] Vite/React 前端页面
- [ ] SSE 流消费逻辑
- [ ] 本地文件系统落盘（如 `logs/`、fixture）
- [ ] 本地浏览器自动化

### 3.3 例外申请

| 项目 | 内容 |
|---|---|
| 触发条件 | 需要验证真实模型能力、代理配置、真实 token 消耗或线上等价行为 |
| 必要说明 | 目的、预算、运行频率、失败处理人 |
| 审批要求 | [待填写：负责人 / reviewer / issue 链接] |

---

## 4. 断言规范

### 4.1 LLM 输出断言

| 项目 | 内容 |
|---|---|
| 规则 | 对 LLM 输出优先做结构断言、关键字段断言、语义约束断言 |
| 应检查 | `topic`、`risk_level`、`root_causes`、`check_steps`、`sources`、错误分支 |
| 不推荐 | 对整段自然语言逐字快照 |
| 原因 | 模型文本轻微波动不应导致误报；测试应关注系统契约而非措辞 |

### 4.2 前端断言

| 项目 | 内容 |
|---|---|
| 规则 | 优先断言用户可观察行为，而不是内部实现细节 |
| 应检查 | 文本显示、按钮可用性、路由切换、localStorage 副作用、toast、列表状态 |
| 不推荐 | 强绑定内部 hook 调用次数或具体 DOM 层级 |

### 4.3 后端断言

| 项目 | 内容 |
|---|---|
| 规则 | 优先断言 API 契约、SSE 顺序、状态机语义、异常分支和资源清理 |
| 应检查 | 响应体结构、队列语义、幂等性、取消/断开后的清理 |
| 不推荐 | 仅断言日志文本字面内容 |

---

## 5. 测试数据与 Fixture 规范

### 5.1 Fixture 目录

- **前端 fixture**：`[待填写路径]`
- **后端 fixture**：`[待填写路径]`
- **LLM 输出 fixture**：`[待填写路径]`
- **E2E 场景数据**：`[待填写路径]`

### 5.2 命名约定

- [ ] 文件名体现模块 + 场景 + 成功/失败语义
- [ ] 同一 prompt 版本变化需有版本号或日期
- [ ] fixture 必须可读，不允许仅使用难以维护的压缩快照

### 5.3 更新规则

- [ ] 修复产品逻辑后，先确认旧 fixture 是否仍代表目标行为
- [ ] 若更新 fixture，需在 PR 描述中说明“为什么旧 fixture 不再有效”
- [ ] 真实 LLM canary 样本变更需单独记录原因

---

## 6. 运行门禁

### 6.1 本地开发

- [ ] 前端单元测试
- [ ] 后端单元测试
- [ ] 受影响模块的最小集成测试
- [ ] 不要求真实 LLM

### 6.2 PR 必跑

- [ ] 前端 build / type-check / unit tests
- [ ] 后端 pytest（unit + integration）
- [ ] 关键 E2E smoke tests（mock LLM）
- [ ] 不允许真实 LLM 或外网依赖

### 6.3 Nightly / 手动验收

- [ ] 浏览器全流程回归
- [ ] 少量真实 LLM canary
- [ ] 记录 token 成本、失败样本和运行时长

---

## 7. 成本与预算控制

### 7.1 默认原则

- **默认**：自动化测试不得调用真实 LLM
- **允许例外**：仅 Canary / 手动验收 / 明确授权的专项验证

### 7.2 成本上限

| 项目 | 内容 |
|---|---|
| 单次 canary 样本数 | [待填写，例如 3–5 条] |
| 单次最大 token 预算 | [待填写] |
| 单周预算上限 | [待填写] |
| 超预算处理 | [待填写：自动停止 / 仅告警 / 人工审批] |

### 7.3 成本记录

- [ ] 每次真实 LLM 测试记录模型名、样本数、运行时间、是否命中预算上限
- [ ] 预算信息进入 CI artifact 或测试报告

---

## 8. 审查清单

### 自动可检查（脚本 / CI）

- [ ] PR 默认测试命令不依赖真实 LLM token
- [ ] 测试环境变量缺失时，mock 测试仍可运行
- [ ] 真实 LLM 测试命令与 PR 默认命令分离
- [ ] E2E 测试可在固定端口和固定 seed 下稳定执行
- [ ] 新增测试目录 / 脚本已写入项目文档

### 人工检查

- [ ] 测试分层是否合理，没有把单元测试写成 E2E
- [ ] LLM 输出断言是否避免逐字快照
- [ ] 真实 LLM 样本是否足够少且具有代表性
- [ ] fixture 是否可维护、可解释
- [ ] 失败后是否能快速判断是代码问题、fixture 过期还是模型波动

---

## 9. 验收标准

- **通过**：PR 默认测试全通过，且不消耗真实 LLM 成本
- **有条件通过**：Canary 失败但已判定为模型波动，且不影响本次代码契约
- **打回**：
  - 任一默认测试需要真实 token 才能通过
  - 测试断言依赖不稳定文案快照
  - 新增关键流程没有对应测试分层归属

---

## 10. 速查词汇表

| 标准术语 | 含义 | 禁用同义词 |
|---|---|---|
| 单元测试 | 隔离单个模块/函数/组件行为的测试 | 小测试、局部联调 |
| 集成测试 | 多模块在受控依赖下的契约测试 | 半 E2E、接口 smoke（不加说明时） |
| E2E | 从用户入口到结果展示的浏览器流程测试 | 全链路单测 |
| Canary | 少量真实依赖抽检测试 | 常规 CI 测试 |
| Mock | 受控替代依赖输出 | 随机假数据 |
| Fixture | 固定可复现的测试样本 | 临时数据、手填数据 |

---

## 11. 已确定实现项

### 11.1 前端测试框架

- **单元/组件测试**：`Vitest + React Testing Library + jsdom`
- **E2E 浏览器测试**：`Playwright`
- **SSE mock 方式**：`page.route('/diagnosis/run', handler)` 原生拦截，返回固定 SSE 文本 fixture
- **不引入 MSW**：`diagnosisApi.ts` 使用 `fetch + ReadableStream` 自定义解析，MSW 模拟 streaming response 的成本远超收益；组件测试直接 `vi.mock('@/services/diagnosisApi')` mock `streamDiagnosis` 函数

### 11.2 前端目录与命令（待落地）

- 单元/组件测试：`frontend/src/**/*.test.tsx` / `frontend/src/**/*.test.ts`
- E2E 测试：`frontend/tests/e2e/*.spec.ts`
- **运行命令尚未创建**：`package.json` 目前无 `test` script，Vitest 也未安装。实施时需先完成以下步骤：
  1. `npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom`
  2. 在 `vite.config.ts` 添加 `test` 配置块
  3. 在 `package.json` `scripts` 中添加 `"test": "vitest run"` 和 `"test:watch": "vitest"`
  4. `npm install -D @playwright/test` 并执行 `npx playwright install`
- 命令确认后更新本条目为已落地

### 11.3 冻结文件的 mock 策略

`useSSEDiagnosis.ts` 和 `diagnosisStore.ts` 为架构约束冻结文件。所有依赖这两个文件的组件测试，**必须在 Vitest 里 mock 整个模块**：

```typescript
vi.mock('@/hooks/useSSEDiagnosis')
vi.mock('@/store/diagnosisStore')
```

不允许在组件测试里让这两个文件真实执行，否则失败无法归因到组件本身。

### 11.4 后端 LangGraph stub 策略

路由层已通过 `Depends(get_graph)` 注入图依赖（`app.api.deps`）。**后端集成测试的正确 stub 点是 `app.dependency_overrides`**，而非 monkeypatch 模块全局。

```python
# conftest.py 标准写法
from httpx import AsyncClient, ASGITransport
from app.api.deps import get_graph, get_auto_diagnosis_service

@pytest.fixture
def fake_graph():
    # 返回一个带 astream_events() 方法的 stub 对象，yield 固定 event sequence
    ...

@pytest.fixture
async def client(fake_graph):
    app.dependency_overrides[get_graph] = lambda: fake_graph
    # httpx ≥ 0.28 移除了 app= 参数，必须用 ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()   # 必须 teardown，防止 lru_cache 污染跨测试
```

**不使用 `monkeypatch.setattr` patch node 函数**：`dependency_overrides` 是 FastAPI 官方测试机制，覆盖更干净；node-level patch 仅用于纯单元测试节点内部行为。

### 11.5 后端 fixture 目录

```
backend/tests/
  unit/
  integration/
  fixtures/
    llm/
      symptom_parser/    # *.json — stub node 输出
      reasoning/
      report_gen/
    sse/                 # *.txt — 原始 SSE 文本，供 page.route() 使用
    sensor/              # FaultSummary fixture
```

### 11.6 嵌入模型与后台服务隔离

后端集成测试（Layer 2）必须在 conftest 里 patch retriever，**禁止加载 ~4GB 本地嵌入模型**。

retriever 的实际入口在 `app.agents.retrieval.get_retriever(corpus)`，是模块级懒加载函数（`app.api.deps` 中**没有** `get_retriever`）：

```python
@pytest.fixture(autouse=True)
def mock_retriever(monkeypatch):
    monkeypatch.setattr(
        "app.agents.retrieval.get_retriever",
        lambda corpus: FakeRetriever(),
    )
```

测试环境变量必须强制设置：

```bash
AUTO_RANDOM_PROBLEMS_GEN=false    # 禁止后台轮询污染测试状态机
SENSOR_POLL_INTERVAL=999          # 防止意外触发
```

### 11.7 真实 LLM canary 触发方式

- 触发方式：`pytest -m canary`（与 PR 默认命令隔离）
- 默认 CI 命令不包含 `canary` marker
- 每次运行记录：模型名、样本数、token 用量、运行时长，输出至 `backend/tests/canary_report.json`

### 11.8 token 预算约束（当前项目规模）

| 项目 | 数值 |
|---|---|
| 单次 canary 样本数 | 3–5 条 |
| 单次最大 token 预算 | 20,000 tokens |
| 单周预算上限 | 100,000 tokens |
| 超预算处理 | 自动停止并记录，不中断 CI |

---

## 12. 变更日志

| 版本 | 日期 | 变更摘要 |
|---|---|---|
| 0.1 | 2026-03-12 | 初始骨架；覆盖测试分层、mock 边界、LLM 成本控制、门禁与术语 |
| 0.2 | 2026-03-12 | 确定工具选型（去掉 MSW，改用 page.route()）；明确 Layer 2/3 边界与失败归因；确定 LangGraph stub 策略（dependency_overrides）；补充嵌入模型隔离、冻结文件 mock 策略、canary 触发方式与 token 预算 |
| 0.3 | 2026-03-12 | 修正 §11.6 retriever stub 点（`app.agents.retrieval.get_retriever`，非不存在的 `app.api.deps.get_retriever`）；将 §11.2 前端命令降级为待落地项（当前 package.json 无 test script，Vitest 未安装）|
| 0.4 | 2026-03-12 | 修正 §11.4 AsyncClient 用法（httpx ≥ 0.28 移除 `app=` 参数，改用 `ASGITransport(app=app)`）|
