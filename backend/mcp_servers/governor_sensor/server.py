"""
FastMCP Server — 调速器油压传感器
topic key: governor_oil_pressure
"""

from datetime import UTC, datetime

from fastmcp import FastMCP

from ..shared.pseudo_random import PseudoRandomEngine, _alarm_state, unit_tag
from ..shared.schemas import SensorPoint, SensorReport
from ..shared.symptom_corpus import GOVERNOR_CORPUS
from ..shared.thresholds import GOVERNOR_THRESHOLDS, TagSpec

mcp = FastMCP("governor-sensor")

_engines: dict[str, PseudoRandomEngine] = {}


def _get_engine(unit_id: str) -> PseudoRandomEngine:
    if unit_id not in _engines:
        _engines[unit_id] = PseudoRandomEngine(f"governor:{unit_id}")
    return _engines[unit_id]


def _compute_point(
    engine: PseudoRandomEngine,
    spec: TagSpec,
    affected: list[str],
    unit_id: str,
) -> SensorPoint:
    value, trend = engine.compute_point_value(
        spec.tag,
        spec.base_val,
        spec.fault_target,
        spec.noise_pct,
        affected,
    )
    state = _alarm_state(value, spec.thresholds)
    return SensorPoint(
        tag=f"HYDRO.{unit_tag(unit_id)}.GOV.{spec.tag}",
        name_cn=spec.name_cn,
        value=round(value, 4),
        thresholds=spec.thresholds,
        alarm_state=state,
        trend=trend,
        timestamp=datetime.now(tz=UTC),
    )


def _select_corpus(anomalies: list[SensorPoint], all_readings: list[SensorPoint]) -> str | None:
    if not anomalies:
        return None

    tags = {p.tag.split(".")[-1] for p in anomalies}
    readings_by_tag = {p.tag.split(".")[-1]: p for p in all_readings}

    pressure_point = readings_by_tag.get("OIL_PRESSURE")
    if pressure_point is None:
        return None

    pressure_val = pressure_point.value
    trip_val = pressure_point.thresholds.trip or 4.41
    normal_val = (
        pressure_point.thresholds.normal_min + pressure_point.thresholds.normal_max
    ) / 2

    # 接近跳机
    if pressure_val <= trip_val * 1.05:
        return GOVERNOR_CORPUS["pressure_critical"].format_map(
            {"value": pressure_val, "trip": trip_val}
        )

    # 备用泵/主泵频繁启动
    if "BACKUP_PUMP_START" in tags or "MAIN_PUMP_START" in tags:
        return GOVERNOR_CORPUS["pump_frequent_start"].format_map(
            {"value": pressure_val}
        )

    # 压力预警
    if "OIL_PRESSURE" in tags:
        return GOVERNOR_CORPUS["pressure_low_warn"].format_map(
            {"value": pressure_val, "normal": normal_val}
        )

    # fallback
    worst = anomalies[0]
    return f"{worst.name_cn} 异常（{worst.value:.3f} {worst.thresholds.unit}）"


@mcp.tool()
def read_sensor_state(unit_id: str) -> SensorReport:
    """读取指定机组当前调速器油压传感器状态"""
    engine = _get_engine(unit_id)
    all_tags = [s.tag for s in GOVERNOR_THRESHOLDS]
    affected = engine.affected_params(all_tags) if engine.is_fault_epoch() else []

    readings = [_compute_point(engine, spec, affected, unit_id) for spec in GOVERNOR_THRESHOLDS]
    anomalies = [r for r in readings if r.alarm_state != "normal"]
    corpus = _select_corpus(anomalies, readings) if anomalies else None

    return SensorReport(
        sensor_id="governor_sensor",
        fault_type="governor_oil_pressure",
        unit_id=unit_id,
        readings=readings,
        has_anomaly=bool(anomalies),
        anomaly_points=anomalies,
        epoch_num=engine._epoch_num(),
        epoch_elapsed_s=engine._elapsed(),
        symptom_corpus=corpus,
    )


@mcp.tool()
def get_sensor_metadata() -> dict:
    """返回调速器油压传感器测点定义和门限规格（静态元数据）"""
    return {
        "sensor_id": "governor_sensor",
        "fault_type": "governor_oil_pressure",
        "thresholds": [
            {
                "tag": s.tag,
                "name_cn": s.name_cn,
                **s.thresholds.model_dump(),
            }
            for s in GOVERNOR_THRESHOLDS
        ],
    }


if __name__ == "__main__":
    mcp.run()
