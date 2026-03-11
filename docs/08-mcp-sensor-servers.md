> **适用场景**：修改或新增 MCP 传感器 Server、伪随机故障引擎、门限常量、现象语料模板时

# MCP 传感器 Server — 设计与实现

无法获取真实电厂 L3 实时数据，通过三个 FastMCP Server 模拟水电机组传感器，
门限值直接对齐知识库（L2.SUPPORT.RULE.001），用于开发/演示阶段的故障场景复现。

---

## 1. 文件结构

```
backend/mcp_servers/
├── __init__.py
├── shared/
│   ├── __init__.py
│   ├── schemas.py          # Pydantic 数据模型（SensorPoint, SensorReport, ThresholdSpec）
│   ├── thresholds.py       # 三类故障门限常量（TagSpec dataclass）
│   ├── symptom_corpus.py   # 中文现象语料模板（对齐知识库 topic 键）
│   └── pseudo_random.py    # 伪随机引擎（PseudoRandomEngine）
├── vibration_sensor/
│   └── server.py           # FastMCP — 振动摆度（vibration_swing）
├── governor_sensor/
│   └── server.py           # FastMCP — 调速器油压（governor_oil_pressure）
└── bearing_sensor/
    └── server.py           # FastMCP — 轴承温升冷却水（bearing_temp_cooling）
```

---

## 2. 数据模型（schemas.py）

```python
AlarmState = Literal["normal", "warn", "alarm", "trip"]
TrendDir   = Literal["stable", "rising", "falling"]
```

| 类 | 说明 |
|----|------|
| `ThresholdSpec` | 单测点门限规格（normal_min/max, warn, alarm, trip, unit, higher_is_worse） |
| `SensorPoint` | 单测点快照（tag, name_cn, value, thresholds, alarm_state, trend, timestamp） |
| `SensorReport` | 整机传感器报告，含所有 readings、anomaly_points、epoch 信息、symptom_corpus |

`higher_is_worse=False` 用于低值报警测点（冷却水压力、进出水温差），此时 `trip/alarm` 判断逻辑取反。

---

## 3. 门限常量（thresholds.py）

每个测点用 `TagSpec` dataclass 封装，同时存储伪随机引擎所需参数：

```python
@dataclass
class TagSpec:
    tag: str
    name_cn: str
    thresholds: ThresholdSpec
    base_val: float       # 正常运行中心值
    fault_target: float   # 故障充分发展时目标值
    noise_pct: float = 0.02
```

### 振动摆度（5 个测点，参考 150MW 级机组）

| Tag | name_cn | normal_max | warn | alarm | trip | unit |
|-----|---------|-----------|------|-------|------|------|
| WATER_GUIDE_RUNOUT | 水导摆度 | 0.20 | 0.30 | 0.45 | 0.60 | mm |
| UPPER_GUIDE_RUNOUT | 上导摆度 | 0.15 | 0.22 | 0.30 | 0.40 | mm |
| TOP_COVER_VIB | 顶盖振动烈度 | 2.8 | 3.5 | 4.5 | 6.0 | mm/s |
| STATOR_FRAME_VIB | 定子机架振动烈度 | 1.5 | 2.0 | 2.5 | 3.5 | mm/s |
| DOMINANT_FREQ_RATIO | 主频/转频比 | 1.1 | — | 0.4（下限） | — | x |

### 调速器油压（5 个测点，额定 6.3 MPa）

| Tag | name_cn | 正常范围 | warn | alarm | trip | unit |
|-----|---------|--------|------|-------|------|------|
| OIL_PRESSURE | 压油罐压力 | 6.0-6.3 | 5.36(85%) | — | 4.41(70%) | MPa |
| BACKUP_PUMP_START | 备用泵启动压力 | 5.50-6.30 | 5.60 | — | — | MPa |
| MAIN_PUMP_START | 主泵启动压力 | 5.70-6.30 | 5.84 | — | — | MPa |
| RELIEF_VALVE_OPEN | 安全阀全开压力 | ≤7.20 | — | 7.20(114%) | — | MPa |
| OIL_TEMP | 油温 | 15-45 | 50 | 55 | 60 | ℃ |

### 轴承温升冷却水（7 个测点）

| Tag | name_cn | normal_max | warn | trip | unit |
|-----|---------|-----------|------|------|------|
| UPPER_GUIDE_TEMP | 上导轴承温度 | 60 | 65 | 70 | ℃ |
| THRUST_TEMP | 推力轴承温度 | 55 | 62 | 70 | ℃ |
| WATER_GUIDE_TEMP | 水导轴承温度 | 60 | 65 | 70 | ℃ |
| BEARING_OIL_TEMP | 轴承油温 | 55 | — | — | ℃ |
| COOLING_WATER_TEMP | 冷却水温度 | 30 | — | — | ℃ |
| COOLING_WATER_PRES | 冷却水压力 | 0.30 | — | 0.10（下限） | MPa |
| DELTA_T | 进出水温差 | 5.0 | — | 0.8（下限→结垢） | ℃ |

> 来源：L2.TOPIC.VIB.001 / RB_TOPIC.VIB / RB_P_001 / RB_P_002 / RB_P_005

---

## 4. 伪随机引擎（pseudo_random.py）

### 4.1 Epoch 机制

```
时间轴（每 300s 为一个 Epoch）：

Epoch N:  |<────────────────── 300s ──────────────────>|
          0s        60s        180s       240s       300s
          ├─ NORMAL ─┤─ PRE-FAULT ─┤──── FAULT ────┤ RESET

• ~60% 概率为 Fault Epoch（全 epoch 确定）
• 故障影响 2-3 个参数（全 epoch 确定）
• t=60-120s：漂移开始（噪声增大，基值缓慢抬升）
• t=120s~：smoothstep 渐进至 fault_target（保证越线）
• t=240-300s：维持在 alarm 附近（±小幅噪声）
```

### 4.2 关键设计原则

- **确定性**：同一 epoch 内多次调用返回平滑渐变值，不随机跳变
- **隔离性**：每台机组（unit_id）和每类传感器（sensor_id）使用独立的种子空间
- **15s 分辨率**：细粒度种子 `elapsed // 15`，同一 15s 窗口内读数平滑

```python
def _rng(self, salt: int = 0) -> random.Random:
    seed = hash(f"{self.sensor_id}:{self._epoch_num()}:{salt}")
    return random.Random(seed)
```

### 4.3 smoothstep 公式

```python
smooth = progress * progress * (3 - 2 * progress)
target = base_val + (fault_target - base_val) * smooth
```

Hermite 插值，确保起止点导数为 0（无突变）。

---

## 5. 现象语料（symptom_corpus.py）

每种故障预定义 2-3 条模板，含 `{value}` 等占位符，MCP Server 用实际读数 `format_map()` 后填充 `SensorReport.symptom_corpus`，可直接作为前端 InputPanel 的初始诊断文本。

| 语料键 | 触发条件 | topic 对齐 |
|--------|----------|-----------|
| `water_guide_runout_alarm` | 水导摆度越 alarm | vibration_swing |
| `top_cover_vib_alarm` | 顶盖振动越 alarm | vibration_swing |
| `compound_vibration` | ≥3 个振动测点超标 | vibration_swing |
| `pressure_low_warn` | 油压下降至 warn | governor_oil_pressure |
| `pressure_critical` | 油压接近 trip | governor_oil_pressure |
| `pump_frequent_start` | 备用/主泵频繁启动 | governor_oil_pressure |
| `bearing_temp_warn` | 轴承温度越 warn | bearing_temp_cooling |
| `bearing_temp_critical` | 轴承温度越 trip | bearing_temp_cooling |
| `cooling_water_fouling` | DELTA_T 低于下限 | bearing_temp_cooling |

---

## 6. MCP Server 接口

每个 server 暴露 2 个 tool：

### `read_sensor_state(unit_id: str) -> SensorReport`

读取指定机组当前传感器状态快照。`unit_id` 格式：`"#1机"` ~ `"#4机"`（纯字符串，与 `DiagnosisRequest.unit_id` 一致）。

### `get_sensor_metadata() -> dict`

返回测点定义和门限规格（静态元数据，无需 unit_id）。

---

## 7. 运行方式

```bash
# standalone 测试（stdio 模式）
cd backend
uv run python -m mcp_servers.vibration_sensor.server

# MCP Inspector 调试
npx @modelcontextprotocol/inspector python -m mcp_servers.vibration_sensor.server

# 导入测试
uv run python -c "
from mcp_servers.vibration_sensor.server import read_sensor_state
r = read_sensor_state('#1机')
print(r.has_anomaly, r.epoch_elapsed_s, r.symptom_corpus)
"
```

---

## 8. config.py 新增配置项

| 变量 | 环境变量 | 默认值 | 说明 |
|------|----------|--------|------|
| `auto_random_problems_gen` | `AUTO_RANDOM_PROBLEMS_GEN` | `False` | 是否启用自动故障生成（FaultAggregator，P2） |
| `sensor_poll_interval_s` | `SENSOR_POLL_INTERVAL` | `15` | 传感器轮询间隔（秒） |
| `fault_collection_window_s` | `FAULT_COLLECTION_WINDOW` | `60` | 故障收集窗口（秒） |
| `diagnosis_cooldown_s` | `DIAGNOSIS_COOLDOWN` | `300` | 同一机组诊断冷却期（秒，避免重复触发） |
| `fault_queue_max` | `FAULT_QUEUE_MAX` | `5` | 待诊断故障队列最大长度 |

---

## 9. FaultAggregator（已实现）

`backend/mcp_servers/fault_aggregator.py`

### 9.1 接口

```python
agg = FaultAggregator(cooldown_s=300)
summary = agg.poll("#1机")      # FaultSummary | None
await agg.run_polling_loop(unit_ids, interval_s=15, on_fault=callback)
```

`FaultSummary` 字段：`unit_id`, `fault_types`, `anomaly_points`, `symptom_text`, `sensor_reports`, `has_fault`

### 9.2 FastAPI 生命周期集成

在 `backend/app/main.py` lifespan 中，通过 `AUTO_RANDOM_PROBLEMS_GEN=true` 启用后台任务：

```bash
AUTO_RANDOM_PROBLEMS_GEN=true uvicorn app.main:app
# 启动时日志：FaultAggregator started | units=['#1机', '#2机', '#3机', '#4机'] poll_interval=15s
```

- 启动：`asyncio.create_task(agg.run_polling_loop(...))` 挂入 lifespan
- 关闭：`task.cancel()` + `await task`（捕获 `CancelledError`），干净退出
- 默认关闭（`AUTO_RANDOM_PROBLEMS_GEN=false`）：不占资源，不影响正常诊断路由

### 9.3 轮询 vs 观察者 trade-off

| 维度 | 轮询（当前） | 观察者/事件推送 |
|------|------------|----------------|
| 实现复杂度 | 低，纯函数调用 | 高，需 broker + 重连逻辑 |
| 传感器侧要求 | 无（只需 read API） | 必须支持 push |
| 故障发现延迟 | 最大 = poll_interval | 接近实时（ms 级） |
| 空闲 CPU | 固定 O(机组 × 传感器) | 零轮询，事件驱动 |
| 可测性 | 易（mock reader 函数） | 难（需 mock broker） |

**升级触发条件**：机组数 > 8 或需秒级响应时，迁移至 OPC-UA Subscription / MQTT 推送。

---

## 10. 下一步（P3）

- **LangGraph 集成**：`on_fault` 回调触发 LangGraph 诊断流，将 `FaultSummary.symptom_text` 注入 `symptom_parser` 节点
- **前端 SensorPanel**：展示实时 `SensorReport`，高亮 `anomaly_points`，提供"一键诊断"入口
