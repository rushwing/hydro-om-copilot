"""
Unit tests for FaultAggregator.

契约：
1. 无异常 → has_fault=False，symptom_text 为空，不触发冷却
2. 有异常且不在冷却期 → 返回 FaultSummary，记录冷却
3. 有异常但在冷却期 → 返回 None（抑制重复触发）
4. 冷却期过后可再次触发
5. reset_cooldown 立即解除冷却
6. cooldown_remaining 返回正确剩余秒数
7. 多传感器异常正确合并：fault_types / anomaly_points / symptom_text
8. symptom_text 包含语料时优先用语料；无语料时退化为测点列表
9. run_polling_loop 调用 on_fault 回调的次数符合冷却预期
"""

import asyncio
import time
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from mcp_servers.fault_aggregator import FaultAggregator, FaultSummary
from mcp_servers.shared.schemas import SensorPoint, SensorReport, ThresholdSpec

# ─── fixture helpers ─────────────────────────────────────────────────────────

def _make_threshold(higher=True) -> ThresholdSpec:
    return ThresholdSpec(
        normal_min=0.0, normal_max=10.0,
        warn=8.0, alarm=9.0, trip=10.0,
        unit="mm", higher_is_worse=higher,
    )


def _make_point(tag="HYDRO.U1.VIB.FAKE", alarm_state="alarm", value=9.5) -> SensorPoint:
    return SensorPoint(
        tag=tag,
        name_cn="测试点",
        value=value,
        thresholds=_make_threshold(),
        alarm_state=alarm_state,
        trend="rising",
        timestamp=datetime.now(tz=UTC),
    )


def _normal_report(sensor_id="vibration_sensor", fault_type="vibration_swing") -> SensorReport:
    pt = _make_point(alarm_state="normal", value=5.0)
    return SensorReport(
        sensor_id=sensor_id,
        fault_type=fault_type,
        unit_id="#1机",
        readings=[pt],
        has_anomaly=False,
        anomaly_points=[],
        epoch_num=1,
        epoch_elapsed_s=10,
        symptom_corpus=None,
    )


def _fault_report(
    sensor_id="vibration_sensor",
    fault_type="vibration_swing",
    corpus: str | None = "水导摆度升高至 0.52 mm",
) -> SensorReport:
    pt = _make_point()
    return SensorReport(
        sensor_id=sensor_id,
        fault_type=fault_type,
        unit_id="#1机",
        readings=[pt],
        has_anomaly=True,
        anomaly_points=[pt],
        epoch_num=1,
        epoch_elapsed_s=270,
        symptom_corpus=corpus,
    )


def _make_aggregator(
    reports: list[SensorReport],
    cooldown_s: int = 300,
) -> FaultAggregator:
    """构造使用 mock reader 的 FaultAggregator。"""
    readers = [MagicMock(return_value=r) for r in reports]
    return FaultAggregator(cooldown_s=cooldown_s, sensor_readers=readers)


# ─── 无异常场景 ───────────────────────────────────────────────────────────────

class TestNoFault:
    def test_all_normal_returns_summary_with_no_fault(self):
        agg = _make_aggregator([_normal_report(), _normal_report(), _normal_report()])
        result = agg.poll("#1机")
        assert result is not None
        assert not result.has_fault
        assert result.fault_types == []
        assert result.anomaly_points == []
        assert result.symptom_text == ""

    def test_no_fault_does_not_start_cooldown(self):
        agg = _make_aggregator([_normal_report()])
        agg.poll("#1机")
        assert agg.cooldown_remaining("#1机") == 0

    def test_no_fault_poll_always_returns_summary(self):
        agg = _make_aggregator([_normal_report()])
        for _ in range(5):
            result = agg.poll("#1机")
            assert result is not None
            assert not result.has_fault


# ─── 故障触发与冷却 ───────────────────────────────────────────────────────────

class TestFaultTrigger:
    def test_fault_first_poll_returns_summary(self):
        agg = _make_aggregator([_fault_report()])
        result = agg.poll("#1机")
        assert result is not None
        assert result.has_fault

    def test_fault_starts_cooldown(self):
        agg = _make_aggregator([_fault_report()], cooldown_s=300)
        agg.poll("#1机")
        assert agg.cooldown_remaining("#1机") > 0

    def test_fault_second_poll_in_cooldown_returns_none(self):
        agg = _make_aggregator([_fault_report()], cooldown_s=300)
        agg.poll("#1机")
        result = agg.poll("#1机")
        assert result is None

    def test_fault_after_cooldown_triggers_again(self):
        agg = _make_aggregator([_fault_report()], cooldown_s=1)
        agg.poll("#1机")
        # 等冷却过期
        time.sleep(1.1)
        result = agg.poll("#1机")
        assert result is not None
        assert result.has_fault

    def test_cooldown_remaining_before_trigger_is_zero(self):
        agg = _make_aggregator([_fault_report()])
        assert agg.cooldown_remaining("#1机") == 0

    def test_cooldown_remaining_after_trigger_is_positive(self):
        agg = _make_aggregator([_fault_report()], cooldown_s=300)
        agg.poll("#1机")
        remaining = agg.cooldown_remaining("#1机")
        assert 0 < remaining <= 300

    def test_reset_cooldown_allows_retrigger(self):
        agg = _make_aggregator([_fault_report()], cooldown_s=300)
        agg.poll("#1机")
        assert agg.poll("#1机") is None  # 冷却中
        agg.reset_cooldown("#1机")
        result = agg.poll("#1机")
        assert result is not None
        assert result.has_fault

    def test_different_units_have_independent_cooldowns(self):
        r = _fault_report()
        readers = [MagicMock(return_value=r)]
        agg = FaultAggregator(cooldown_s=300, sensor_readers=readers)
        agg.poll("#1机")
        # #2机 未触发，不受 #1机 冷却影响
        result = agg.poll("#2机")
        assert result is not None
        assert result.has_fault


# ─── 多传感器汇总 ─────────────────────────────────────────────────────────────

class TestMultiSensorAggregation:
    def test_fault_types_aggregated(self):
        reports = [
            _fault_report("vibration_sensor", "vibration_swing"),
            _fault_report("governor_sensor", "governor_oil_pressure"),
            _normal_report("bearing_sensor", "bearing_temp_cooling"),
        ]
        agg = _make_aggregator(reports)
        result = agg.poll("#1机")
        assert result is not None
        assert set(result.fault_types) == {"vibration_swing", "governor_oil_pressure"}

    def test_anomaly_points_merged_from_all_sensors(self):
        r1 = _fault_report("vibration_sensor", "vibration_swing", corpus=None)
        r2 = _fault_report("governor_sensor", "governor_oil_pressure", corpus=None)
        # Each fault report has 1 anomaly point
        agg = _make_aggregator([r1, r2, _normal_report()])
        result = agg.poll("#1机")
        assert result is not None
        assert len(result.anomaly_points) == 2

    def test_sensor_reports_all_included(self):
        reports = [
            _normal_report("vibration_sensor", "vibration_swing"),
            _fault_report("governor_sensor", "governor_oil_pressure"),
            _normal_report("bearing_sensor", "bearing_temp_cooling"),
        ]
        agg = _make_aggregator(reports)
        result = agg.poll("#1机")
        assert result is not None
        assert len(result.sensor_reports) == 3


# ─── symptom_text 拼装 ────────────────────────────────────────────────────────

class TestSymptomText:
    def test_single_corpus_no_header(self):
        corpus = "水导摆度升高至 0.52 mm（报警值 0.45 mm）"
        agg = _make_aggregator([_fault_report(corpus=corpus)])
        result = agg.poll("#1机")
        assert result is not None
        assert corpus in result.symptom_text
        # 单条语料不加"出现以下异常"前缀
        assert "出现以下异常" not in result.symptom_text

    def test_multiple_corpus_joined_with_separator(self):
        c1 = "水导摆度升高至 0.52 mm"
        c2 = "调速器压力下降至 5.20 MPa"
        agg = _make_aggregator([
            _fault_report("vibration_sensor", "vibration_swing", corpus=c1),
            _fault_report("governor_sensor", "governor_oil_pressure", corpus=c2),
        ])
        result = agg.poll("#1机")
        assert result is not None
        assert c1 in result.symptom_text
        assert c2 in result.symptom_text
        assert "；" in result.symptom_text  # separator

    def test_no_corpus_falls_back_to_point_list(self):
        agg = _make_aggregator([_fault_report(corpus=None)])
        result = agg.poll("#1机")
        assert result is not None
        # 退化格式包含 unit_id 和测点名
        assert "#1机" in result.symptom_text or "传感器异常" in result.symptom_text
        assert "测试点" in result.symptom_text

    def test_no_anomaly_symptom_text_empty(self):
        agg = _make_aggregator([_normal_report()])
        result = agg.poll("#1机")
        assert result is not None
        assert result.symptom_text == ""


# ─── run_polling_loop ────────────────────────────────────────────────────────

class TestPollingLoop:
    @pytest.mark.asyncio
    async def test_on_fault_called_once_within_cooldown(self):
        """故障期间循环多次，on_fault 只被调用一次（冷却抑制后续）。"""
        reports = [_fault_report()]
        readers = [MagicMock(return_value=r) for r in reports]
        agg = FaultAggregator(cooldown_s=300, sensor_readers=readers)

        calls: list[FaultSummary] = []

        async def _run():
            await asyncio.wait_for(
                agg.run_polling_loop(["#1机"], interval_s=0, on_fault=calls.append),
                timeout=0.05,
            )

        try:
            await _run()
        except TimeoutError:
            pass

        assert len(calls) == 1, f"Expected 1 call, got {len(calls)}"

    @pytest.mark.asyncio
    async def test_on_fault_not_called_when_normal(self):
        """无故障时 on_fault 不被调用。"""
        agg = FaultAggregator(
            cooldown_s=300,
            sensor_readers=[MagicMock(return_value=_normal_report())],
        )
        calls: list[FaultSummary] = []

        async def _run():
            await asyncio.wait_for(
                agg.run_polling_loop(["#1机"], interval_s=0, on_fault=calls.append),
                timeout=0.05,
            )

        try:
            await _run()
        except TimeoutError:
            pass

        assert len(calls) == 0


# ─── 异常隔离（P1 契约）────────────────────────────────────────────────────────

class TestPollingLoopErrorIsolation:
    """
    单机组 poll() 或 on_fault() 抛异常时，
    polling loop 不应终止，其余机组必须继续被轮询。
    """

    async def _run_briefly(self, agg: FaultAggregator, unit_ids: list[str], on_fault=None):
        try:
            await asyncio.wait_for(
                agg.run_polling_loop(unit_ids, interval_s=0, on_fault=on_fault),
                timeout=0.08,
            )
        except TimeoutError:
            pass

    @pytest.mark.asyncio
    async def test_poll_exception_does_not_kill_loop(self):
        """某机组 poll() 抛异常，其他机组仍继续被轮询。"""
        good_reader = MagicMock(return_value=_fault_report())
        bad_reader = MagicMock(side_effect=RuntimeError("sensor unreachable"))

        calls: list[FaultSummary] = []
        agg = FaultAggregator(cooldown_s=0, sensor_readers=[bad_reader, good_reader])

        # 两台机组：#1机 reader 会抛异常（bad_reader first），但 #2机 应正常收到故障
        # 注意：两台机组共享同一组 readers，都会触发 bad_reader
        # 改用只对 #1机 注入异常的策略：patching poll 直接

        # 直接 patch poll：#1机 抛异常，#2机 返回故障
        original_poll = agg.poll

        def selective_poll(uid):
            if uid == "#1机":
                raise RuntimeError("transient error")
            return original_poll(uid)

        agg.poll = selective_poll  # type: ignore[method-assign]

        good_readers = [MagicMock(return_value=_fault_report())]
        agg._readers = good_readers

        await self._run_briefly(agg, ["#1机", "#2机"], on_fault=calls.append)

        # #2机 应至少触发过一次 on_fault
        assert any(s.unit_id == "#2机" for s in calls), (
            "Loop killed by #1机 exception — #2机 never polled"
        )

    @pytest.mark.asyncio
    async def test_on_fault_exception_does_not_kill_loop(self):
        """on_fault 回调抛异常，polling loop 不应终止，下一轮仍继续。"""
        call_count = 0

        def flaky_callback(summary: FaultSummary) -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("callback failure")

        # 使用 cooldown_s=0 使得每轮都会触发 on_fault
        agg = FaultAggregator(
            cooldown_s=0,
            sensor_readers=[MagicMock(return_value=_fault_report())],
        )

        await self._run_briefly(agg, ["#1机"], on_fault=flaky_callback)

        # 若 loop 正常存活，callback 应被调用多次（cooldown=0 每轮都触发）
        assert call_count > 1, (
            f"Loop exited after first callback exception (call_count={call_count})"
        )

    @pytest.mark.asyncio
    async def test_cancelled_error_propagates(self):
        """CancelledError 必须透传，不被 try/except 吞掉（保证 shutdown 正常）。"""
        agg = FaultAggregator(
            cooldown_s=300,
            sensor_readers=[MagicMock(return_value=_normal_report())],
        )

        task = asyncio.create_task(
            agg.run_polling_loop(["#1机"], interval_s=10)
        )
        await asyncio.sleep(0)  # 让任务启动
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task
