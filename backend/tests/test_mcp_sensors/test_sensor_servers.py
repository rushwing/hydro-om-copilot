"""
Unit tests for the three MCP sensor servers.

契约：
1. SensorReport 字段完整、类型正确
2. tag 前缀随 unit_id 变化（不硬编码 U1）
3. 正常 epoch 下所有读数在 normal 范围内
4. 故障 epoch 充分发展后 anomaly_points 非空
5. 有异常时 symptom_corpus 非 None，无异常时为 None
6. get_sensor_metadata 返回正确的 sensor_id 和 fault_type
"""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from mcp_servers.bearing_sensor.server import (
    get_sensor_metadata as brg_meta,
)
from mcp_servers.bearing_sensor.server import (
    read_sensor_state as brg_read,
)
from mcp_servers.governor_sensor.server import (
    get_sensor_metadata as gov_meta,
)
from mcp_servers.governor_sensor.server import (
    read_sensor_state as gov_read,
)
from mcp_servers.shared.pseudo_random import PseudoRandomEngine
from mcp_servers.shared.schemas import AlarmState, SensorReport
from mcp_servers.vibration_sensor.server import (
    get_sensor_metadata as vib_meta,
)
from mcp_servers.vibration_sensor.server import (
    read_sensor_state as vib_read,
)

# ─── helpers ─────────────────────────────────────────────────────────────────

def _force_normal_epoch(engine: PseudoRandomEngine):
    """Patch engine so is_fault_epoch() returns False."""
    return patch.object(engine, "is_fault_epoch", return_value=False)


def _force_fault_epoch_late(engine: PseudoRandomEngine, elapsed: int = 270):
    """Patch engine: fault epoch, late stage (elapsed past fault_start)."""
    patches = [
        patch.object(engine, "is_fault_epoch", return_value=True),
        patch.object(type(engine), "_elapsed", return_value=elapsed),
    ]
    return patches


# ─── SensorReport schema ─────────────────────────────────────────────────────

class TestSensorReportSchema:
    @pytest.mark.parametrize(
        "read_fn, sensor_id, fault_type",
        [
            (vib_read, "vibration_sensor", "vibration_swing"),
            (gov_read, "governor_sensor", "governor_oil_pressure"),
            (brg_read, "bearing_sensor", "bearing_temp_cooling"),
        ],
    )
    def test_report_fields(self, read_fn, sensor_id, fault_type):
        report = read_fn("#1机")
        assert isinstance(report, SensorReport)
        assert report.sensor_id == sensor_id
        assert report.fault_type == fault_type
        assert report.unit_id == "#1机"
        assert isinstance(report.has_anomaly, bool)
        assert isinstance(report.epoch_num, int)
        assert 0 <= report.epoch_elapsed_s < 300
        assert isinstance(report.readings, list)
        assert len(report.readings) > 0

    @pytest.mark.parametrize("read_fn", [vib_read, gov_read, brg_read])
    def test_each_point_has_valid_alarm_state(self, read_fn):
        report = read_fn("#1机")
        valid: set[AlarmState] = {"normal", "warn", "alarm", "trip"}
        for pt in report.readings:
            assert pt.alarm_state in valid, f"{pt.tag}: {pt.alarm_state!r}"

    @pytest.mark.parametrize("read_fn", [vib_read, gov_read, brg_read])
    def test_timestamp_is_utc(self, read_fn):
        report = read_fn("#1机")
        for pt in report.readings:
            assert pt.timestamp.tzinfo is not None
            # Within 5 seconds of now
            delta = abs((datetime.now(tz=UTC) - pt.timestamp).total_seconds())
            assert delta < 5

    @pytest.mark.parametrize("read_fn", [vib_read, gov_read, brg_read])
    def test_anomaly_points_subset_of_readings(self, read_fn):
        report = read_fn("#1机")
        reading_tags = {p.tag for p in report.readings}
        for pt in report.anomaly_points:
            assert pt.tag in reading_tags
        assert report.has_anomaly == (len(report.anomaly_points) > 0)


# ─── unit_id → tag 映射 (P1) ─────────────────────────────────────────────────

class TestUnitTagInReport:
    @pytest.mark.parametrize(
        "unit_id, expected_prefix",
        [
            ("#1机", "HYDRO.U1.VIB."),
            ("#2机", "HYDRO.U2.VIB."),
            ("#3机", "HYDRO.U3.VIB."),
            ("#4机", "HYDRO.U4.VIB."),
        ],
    )
    def test_vibration_tag_prefix(self, unit_id, expected_prefix):
        report = vib_read(unit_id)
        for pt in report.readings:
            assert pt.tag.startswith(expected_prefix), (
                f"unit_id={unit_id!r}: tag {pt.tag!r} should start with {expected_prefix!r}"
            )

    @pytest.mark.parametrize(
        "unit_id, expected_prefix",
        [
            ("#1机", "HYDRO.U1.GOV."),
            ("#2机", "HYDRO.U2.GOV."),
        ],
    )
    def test_governor_tag_prefix(self, unit_id, expected_prefix):
        report = gov_read(unit_id)
        for pt in report.readings:
            assert pt.tag.startswith(expected_prefix)

    @pytest.mark.parametrize(
        "unit_id, expected_prefix",
        [
            ("#1机", "HYDRO.U1.BRG."),
            ("#3机", "HYDRO.U3.BRG."),
        ],
    )
    def test_bearing_tag_prefix(self, unit_id, expected_prefix):
        report = brg_read(unit_id)
        for pt in report.readings:
            assert pt.tag.startswith(expected_prefix)

    def test_different_units_have_different_tags(self):
        r1 = vib_read("#1机")
        r2 = vib_read("#2机")
        tags1 = {p.tag for p in r1.readings}
        tags2 = {p.tag for p in r2.readings}
        assert tags1.isdisjoint(tags2), "Unit #1 and #2 share tag names — still hardcoded?"


# ─── 正常 epoch → 所有读数在范围内 ───────────────────────────────────────────

class TestNormalEpoch:
    def _check_all_normal(self, report: SensorReport):
        """在 normal epoch 下，所有测点应处于 normal 状态。"""
        for pt in report.readings:
            assert pt.alarm_state == "normal", (
                f"{pt.tag}: alarm_state={pt.alarm_state!r}, value={pt.value}"
            )
        assert not report.has_anomaly
        assert report.symptom_corpus is None

    def test_vibration_normal_epoch(self):
        from mcp_servers.vibration_sensor import server as vib_srv
        engine = vib_srv._get_engine("#1机-normal-test")
        with _force_normal_epoch(engine):
            report = vib_read("#1机-normal-test")
        self._check_all_normal(report)

    def test_governor_normal_epoch(self):
        from mcp_servers.governor_sensor import server as gov_srv
        engine = gov_srv._get_engine("#1机-normal-gov")
        with _force_normal_epoch(engine):
            report = gov_read("#1机-normal-gov")
        self._check_all_normal(report)

    def test_bearing_normal_epoch(self):
        from mcp_servers.bearing_sensor import server as brg_srv
        engine = brg_srv._get_engine("#1机-normal-brg")
        with _force_normal_epoch(engine):
            report = brg_read("#1机-normal-brg")
        self._check_all_normal(report)


# ─── 故障 epoch 充分发展后 anomaly_points 非空 ───────────────────────────────

class TestFaultEpoch:
    def test_vibration_late_fault_has_anomalies(self):
        from mcp_servers.vibration_sensor import server as vib_srv
        engine = vib_srv._get_engine("#1机-fault-test")
        patches = _force_fault_epoch_late(engine, elapsed=270)
        with patches[0], patches[1]:
            report = vib_read("#1机-fault-test")
        assert report.has_anomaly, "Expected anomalies in late fault epoch"
        assert len(report.anomaly_points) >= 1
        assert report.symptom_corpus is not None
        assert len(report.symptom_corpus) > 10

    def test_governor_late_fault_has_anomalies(self):
        from mcp_servers.governor_sensor import server as gov_srv
        engine = gov_srv._get_engine("#1机-fault-gov")
        patches = _force_fault_epoch_late(engine, elapsed=270)
        with patches[0], patches[1]:
            report = gov_read("#1机-fault-gov")
        assert report.has_anomaly
        assert report.symptom_corpus is not None

    def test_bearing_late_fault_has_anomalies(self):
        from mcp_servers.bearing_sensor import server as brg_srv
        engine = brg_srv._get_engine("#1机-fault-brg")
        patches = _force_fault_epoch_late(engine, elapsed=270)
        with patches[0], patches[1]:
            report = brg_read("#1机-fault-brg")
        assert report.has_anomaly
        assert report.symptom_corpus is not None


# ─── get_sensor_metadata ─────────────────────────────────────────────────────

class TestMetadata:
    @pytest.mark.parametrize(
        "meta_fn, sensor_id, fault_type",
        [
            (vib_meta, "vibration_sensor", "vibration_swing"),
            (gov_meta, "governor_sensor", "governor_oil_pressure"),
            (brg_meta, "bearing_sensor", "bearing_temp_cooling"),
        ],
    )
    def test_metadata_structure(self, meta_fn, sensor_id, fault_type):
        meta = meta_fn()
        assert meta["sensor_id"] == sensor_id
        assert meta["fault_type"] == fault_type
        assert isinstance(meta["thresholds"], list)
        assert len(meta["thresholds"]) > 0
        for t in meta["thresholds"]:
            assert "tag" in t
            assert "name_cn" in t
            assert "unit" in t
