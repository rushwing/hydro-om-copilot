"""
FastMCP Server — 轴承温升冷却水传感器
topic key: bearing_temp_cooling
"""

from datetime import UTC, datetime

from fastmcp import FastMCP

from ..shared.pseudo_random import PseudoRandomEngine, _alarm_state, unit_tag
from ..shared.schemas import SensorPoint, SensorReport
from ..shared.symptom_corpus import BEARING_CORPUS
from ..shared.thresholds import BEARING_THRESHOLDS, TagSpec

mcp = FastMCP("bearing-sensor")

_engines: dict[str, PseudoRandomEngine] = {}

_BEARING_TAGS = {"UPPER_GUIDE_TEMP", "THRUST_TEMP", "WATER_GUIDE_TEMP"}


def _get_engine(unit_id: str) -> PseudoRandomEngine:
    if unit_id not in _engines:
        _engines[unit_id] = PseudoRandomEngine(f"bearing:{unit_id}")
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
        tag=f"HYDRO.{unit_tag(unit_id)}.BRG.{spec.tag}",
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

    readings_by_tag = {p.tag.split(".")[-1]: p for p in all_readings}
    anomaly_tags = {p.tag.split(".")[-1] for p in anomalies}

    # 冷却水进出水温差异常（结垢）
    delta_t_point = readings_by_tag.get("DELTA_T")
    if delta_t_point and delta_t_point.alarm_state != "normal":
        return BEARING_CORPUS["cooling_water_fouling"].format_map(
            {"delta_t": delta_t_point.value}
        )

    # 轴承温度 trip 级别
    bearing_anomalies = [
        p for p in anomalies if p.tag.split(".")[-1] in _BEARING_TAGS
    ]
    if bearing_anomalies:
        worst = max(bearing_anomalies, key=lambda p: p.value)
        trip_val = worst.thresholds.trip or 70.0
        alarm_val = worst.thresholds.warn or 65.0
        delta_t_val = delta_t_point.value if delta_t_point else 3.0

        if worst.alarm_state == "trip":
            return BEARING_CORPUS["bearing_temp_critical"].format_map(
                {"bearing_name": worst.name_cn, "value": worst.value, "trip": trip_val}
            )
        else:
            return BEARING_CORPUS["bearing_temp_warn"].format_map(
                {
                    "bearing_name": worst.name_cn,
                    "value": worst.value,
                    "alarm": alarm_val,
                    "delta_t": delta_t_val,
                }
            )

    # 冷却水压力低
    if "COOLING_WATER_PRES" in anomaly_tags:
        p = readings_by_tag["COOLING_WATER_PRES"]
        trip = p.thresholds.trip
        return (
            f"冷却水压力下降至 {p.value:.3f} MPa，"
            f"低于保护值 {trip:.2f} MPa，需检查冷却水供水系统"
        )

    # fallback
    worst = anomalies[0]
    return f"{worst.name_cn} 异常（{worst.value:.3f} {worst.thresholds.unit}）"


@mcp.tool()
def read_sensor_state(unit_id: str) -> SensorReport:
    """读取指定机组当前轴承温升冷却水传感器状态"""
    engine = _get_engine(unit_id)
    all_tags = [s.tag for s in BEARING_THRESHOLDS]
    affected = engine.affected_params(all_tags) if engine.is_fault_epoch() else []

    readings = [_compute_point(engine, spec, affected, unit_id) for spec in BEARING_THRESHOLDS]
    anomalies = [r for r in readings if r.alarm_state != "normal"]
    corpus = _select_corpus(anomalies, readings) if anomalies else None

    return SensorReport(
        sensor_id="bearing_sensor",
        fault_type="bearing_temp_cooling",
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
    """返回轴承温升冷却水传感器测点定义和门限规格（静态元数据）"""
    return {
        "sensor_id": "bearing_sensor",
        "fault_type": "bearing_temp_cooling",
        "thresholds": [
            {
                "tag": s.tag,
                "name_cn": s.name_cn,
                **s.thresholds.model_dump(),
            }
            for s in BEARING_THRESHOLDS
        ],
    }


if __name__ == "__main__":
    mcp.run()
