"""
sensor_reader LangGraph node — auto-diagnosis path only.

Reads serialized SensorReport list from state, formats anomaly points,
and injects a structured sensor summary into stream_tokens for display.
"""

from __future__ import annotations

import logging

from app.agents.state import AgentState

_logger = logging.getLogger("app.agents.sensor_reader")


async def sensor_reader_node(state: AgentState) -> dict:
    """
    Auto-diagnosis only: reads sensor_reports from state, formats anomaly points,
    injects structured sensor summary into stream_tokens for display.
    """
    from mcp_servers.shared.schemas import SensorReport

    sensor_reports_raw = state.get("sensor_reports", [])
    sensor_data: list[dict] = []
    lines = ["【传感器探测结果】"]

    for r_dict in sensor_reports_raw:
        try:
            report = SensorReport.model_validate(r_dict)
        except Exception as exc:
            _logger.warning("failed to parse SensorReport: %s", exc)
            continue

        for pt in report.anomaly_points:
            sensor_data.append(pt.model_dump())
            lines.append(
                f"  {pt.name_cn}: {pt.value:.3f}{pt.thresholds.unit} "
                f"[{pt.alarm_state.upper()}] ↑ {pt.trend}"
            )

    if len(lines) == 1:
        lines.append("  （无异常测点）")

    text = "\n".join(lines) + "\n\n"
    _logger.debug("sensor_reader: %d anomaly points extracted", len(sensor_data))

    return {"sensor_data": sensor_data, "stream_tokens": [text]}
