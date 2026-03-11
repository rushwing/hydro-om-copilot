"""
FastMCP Server — 振动摆度传感器
topic key: vibration_swing
"""

from datetime import UTC, datetime

from fastmcp import FastMCP

from ..shared.pseudo_random import PseudoRandomEngine, _alarm_state
from ..shared.schemas import SensorPoint, SensorReport
from ..shared.symptom_corpus import VIBRATION_CORPUS
from ..shared.thresholds import VIBRATION_THRESHOLDS, TagSpec

mcp = FastMCP("vibration-sensor")

_engines: dict[str, PseudoRandomEngine] = {}


def _get_engine(unit_id: str) -> PseudoRandomEngine:
    if unit_id not in _engines:
        _engines[unit_id] = PseudoRandomEngine(f"vibration:{unit_id}")
    return _engines[unit_id]


def _compute_point(
    engine: PseudoRandomEngine,
    spec: TagSpec,
    affected: list[str],
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
        tag=f"HYDRO.U1.VIB.{spec.tag}",
        name_cn=spec.name_cn,
        value=round(value, 4),
        thresholds=spec.thresholds,
        alarm_state=state,
        trend=trend,
        timestamp=datetime.now(tz=UTC),
    )


def _select_corpus(anomalies: list[SensorPoint]) -> str | None:
    """从异常点中选取最严重的，格式化对应语料字符串。"""
    if not anomalies:
        return None

    tags = {p.tag.split(".")[-1] for p in anomalies}
    readings_by_tag = {p.tag.split(".")[-1]: p for p in anomalies}

    # 复合振动（3 个以上超标）
    if len(anomalies) >= 3:
        vib1 = readings_by_tag.get("WATER_GUIDE_RUNOUT")
        vib2 = readings_by_tag.get("UPPER_GUIDE_RUNOUT")
        vib3 = readings_by_tag.get("TOP_COVER_VIB")
        if vib1 and vib2 and vib3:
            return VIBRATION_CORPUS["compound_vibration"].format_map(
                {"vib1": vib1.value, "vib2": vib2.value, "vib3": vib3.value}
            )

    # 顶盖振动
    if "TOP_COVER_VIB" in tags:
        p = readings_by_tag["TOP_COVER_VIB"]
        return VIBRATION_CORPUS["top_cover_vib_alarm"].format_map({"value": p.value})

    # 水导摆度
    if "WATER_GUIDE_RUNOUT" in tags:
        p = readings_by_tag["WATER_GUIDE_RUNOUT"]
        spec = next(s for s in VIBRATION_THRESHOLDS if s.tag == "WATER_GUIDE_RUNOUT")
        return VIBRATION_CORPUS["water_guide_runout_alarm"].format_map(
            {"value": p.value, "alarm": spec.thresholds.alarm or 0.45}
        )

    # fallback
    worst = max(anomalies, key=lambda p: p.alarm_state != "normal")
    return f"{worst.name_cn} 异常（{worst.value:.3f} {worst.thresholds.unit}）"


@mcp.tool()
def read_sensor_state(unit_id: str) -> SensorReport:
    """读取指定机组当前振动摆度传感器状态"""
    engine = _get_engine(unit_id)
    all_tags = [s.tag for s in VIBRATION_THRESHOLDS]
    affected = engine.affected_params(all_tags) if engine.is_fault_epoch() else []

    readings = [_compute_point(engine, spec, affected) for spec in VIBRATION_THRESHOLDS]
    anomalies = [r for r in readings if r.alarm_state != "normal"]
    corpus = _select_corpus(anomalies) if anomalies else None

    return SensorReport(
        sensor_id="vibration_sensor",
        fault_type="vibration_swing",
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
    """返回振动摆度传感器测点定义和门限规格（静态元数据）"""
    return {
        "sensor_id": "vibration_sensor",
        "fault_type": "vibration_swing",
        "thresholds": [
            {
                "tag": s.tag,
                "name_cn": s.name_cn,
                **s.thresholds.model_dump(),
            }
            for s in VIBRATION_THRESHOLDS
        ],
    }


if __name__ == "__main__":
    mcp.run()
