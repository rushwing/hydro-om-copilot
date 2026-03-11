"""
FaultAggregator — 轮询三个 MCP 传感器 Server，汇总跨传感器故障，
管理诊断冷却期，为 LangGraph symptom_parser 节点提供输入。

设计约束：
- 无外部依赖，纯 Python（不启动 MCP subprocess，直接调用函数）
- 线程安全：冷却时钟使用 monotonic，cooldown dict 仅在单线程 poll() 内修改
- 不写全局状态到磁盘；重启后冷却期重置（演示场景可接受）
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from .bearing_sensor.server import read_sensor_state as _brg_read
from .governor_sensor.server import read_sensor_state as _gov_read
from .shared.schemas import SensorPoint, SensorReport
from .vibration_sensor.server import read_sensor_state as _vib_read

# 三个 sensor 读取函数（可在测试中替换）
_SENSOR_READERS: list[Callable[[str], SensorReport]] = [
    _vib_read,
    _gov_read,
    _brg_read,
]


@dataclass
class FaultSummary:
    """一次故障汇总结果，作为 LangGraph symptom_parser 的输入。"""

    unit_id: str
    fault_types: list[str]        # e.g. ["vibration_swing", "governor_oil_pressure"]
    anomaly_points: list[SensorPoint]  # 所有传感器的异常测点合并
    symptom_text: str             # 拼接后的中文现象描述，可直接注入 LangGraph
    sensor_reports: list[SensorReport]  # 原始报告，供调试和前端展示
    polled_at: float = field(default_factory=time.monotonic)

    @property
    def has_fault(self) -> bool:
        return bool(self.anomaly_points)


class FaultAggregator:
    """
    轮询所有传感器，汇总故障，管理诊断冷却期。

    用法（手动轮询）：
        agg = FaultAggregator(cooldown_s=300)
        summary = agg.poll("#1机")
        if summary and summary.has_fault:
            # 触发 LangGraph 诊断
            pass

    用法（自动轮询，见 run_polling_loop）：
        import asyncio
        asyncio.run(agg.run_polling_loop(["#1机", "#2机"], interval_s=15))
    """

    def __init__(
        self,
        cooldown_s: int = 300,
        sensor_readers: list[Callable[[str], SensorReport]] | None = None,
    ) -> None:
        self._cooldown_s = cooldown_s
        self._readers = sensor_readers if sensor_readers is not None else _SENSOR_READERS
        # unit_id → monotonic timestamp of last diagnosis trigger
        self._last_triggered: dict[str, float] = {}

    # ─── public API ───────────────────────────────────────────────────────────

    def poll(self, unit_id: str) -> FaultSummary | None:
        """
        轮询指定机组所有传感器，返回 FaultSummary。

        - 若当前无任何异常，返回不含异常点的 FaultSummary（has_fault=False）
        - 若在冷却期内，返回 None（抑制重复诊断）
        - 若有异常且不在冷却期，返回完整 FaultSummary 并记录触发时间
        """
        reports = [reader(unit_id) for reader in self._readers]
        summary = self._aggregate(unit_id, reports)

        if not summary.has_fault:
            return summary

        if self._in_cooldown(unit_id):
            return None

        self._last_triggered[unit_id] = time.monotonic()
        return summary

    def reset_cooldown(self, unit_id: str) -> None:
        """手动重置冷却期（测试 / 运维干预）。"""
        self._last_triggered.pop(unit_id, None)

    def cooldown_remaining(self, unit_id: str) -> int:
        """返回剩余冷却秒数，0 表示已过期或未触发过。"""
        last = self._last_triggered.get(unit_id)
        if last is None:
            return 0
        elapsed = time.monotonic() - last
        return max(0, int(self._cooldown_s - elapsed))

    async def run_polling_loop(
        self,
        unit_ids: list[str],
        interval_s: int = 15,
        on_fault: Callable[[FaultSummary], None] | None = None,
    ) -> None:
        """
        异步轮询循环（供后台任务使用）。
        on_fault 回调在检测到故障且不在冷却期时调用。
        """
        import asyncio

        while True:
            for uid in unit_ids:
                summary = self.poll(uid)
                if summary and summary.has_fault and on_fault:
                    on_fault(summary)
            await asyncio.sleep(interval_s)

    # ─── internal ─────────────────────────────────────────────────────────────

    def _aggregate(self, unit_id: str, reports: list[SensorReport]) -> FaultSummary:
        fault_types: list[str] = []
        all_anomalies: list[SensorPoint] = []
        corpus_parts: list[str] = []

        for report in reports:
            if report.has_anomaly:
                fault_types.append(report.fault_type)
                all_anomalies.extend(report.anomaly_points)
                if report.symptom_corpus:
                    corpus_parts.append(report.symptom_corpus)

        symptom_text = self._build_symptom_text(unit_id, corpus_parts, all_anomalies)

        return FaultSummary(
            unit_id=unit_id,
            fault_types=fault_types,
            anomaly_points=all_anomalies,
            symptom_text=symptom_text,
            sensor_reports=reports,
        )

    def _build_symptom_text(
        self,
        unit_id: str,
        corpus_parts: list[str],
        anomalies: list[SensorPoint],
    ) -> str:
        """
        拼装现象描述字符串。
        - 有语料：直接用语料（已包含结构化描述）
        - 无语料但有异常：生成简洁的测点列表
        - 无异常：返回空字符串
        """
        if corpus_parts:
            header = f"{unit_id}出现以下异常：" if len(corpus_parts) > 1 else ""
            return header + "；".join(corpus_parts)

        if anomalies:
            items = "、".join(
                f"{p.name_cn} {p.value:.3f}{p.thresholds.unit}（{p.alarm_state}）"
                for p in anomalies
            )
            return f"{unit_id}传感器异常：{items}"

        return ""

    def _in_cooldown(self, unit_id: str) -> bool:
        last = self._last_triggered.get(unit_id)
        if last is None:
            return False
        return (time.monotonic() - last) < self._cooldown_s
