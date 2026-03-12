"""
Auto-diagnosis runner — 从 FaultSummary 触发 LangGraph 诊断流。

与 /diagnosis/run SSE 路由的区别：
- 使用 ainvoke()（非流式），适合后台任务
- 输入来自传感器 FaultSummary，不来自用户 HTTP 请求
- 结果写入 DiagnosisStore（环形缓冲区），通过 GET /diagnosis/auto-results 可查
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable

from app.agents.graph import get_compiled_graph
from app.store.diagnosis_store import AutoDiagnosisRecord, DiagnosisStore
from app.utils.session_log import create_session_logger, remove_session_logger
from mcp_servers.fault_aggregator import FaultSummary

_logger = logging.getLogger("app.agents.auto_diagnosis")

_AUTO_NODES = {
    "sensor_reader",
    "symptom_parser",
    "image_agent",
    "retrieval",
    "reasoning",
    "report_gen",
}


async def run_auto_diagnosis(
    summary: FaultSummary,
    store: DiagnosisStore,
) -> AutoDiagnosisRecord:
    """
    对 FaultSummary 运行完整 LangGraph 诊断流，将结果写入 store 并返回 record。

    symptom_text 已是结构化中文现象描述，symptom_parser 可直接解析出 topic。
    不预填 topic：保持 graph 路由逻辑唯一入口（symptom_parser._infer_topic）。
    """
    session_id = f"auto-{uuid.uuid4()}"
    graph = get_compiled_graph()

    # 单条语料场景下 symptom_text 不含机组号前缀，显式注入确保
    # symptom_parser 能提取 parsed_symptom.unit_id，避免 report_gen 退化为"未知机组"
    raw_query = (
        summary.symptom_text
        if summary.unit_id in summary.symptom_text
        else f"【{summary.unit_id}】{summary.symptom_text}"
    )

    initial_state = {
        "session_id": session_id,
        "raw_query": raw_query,
        "image_base64": None,
        "parsed_symptom": None,
        "ocr_text": None,
        "topic": None,
        "retrieved": None,
        "root_causes": [],
        "check_steps": [],
        "risk_level": "medium",
        "escalation_required": False,
        "escalation_reason": None,
        "report_draft": None,
        "stream_tokens": [],
        "sensor_reports": [],
        "sensor_data": [],
        "sources": [],
        "error": None,
    }

    try:
        final_state = await graph.ainvoke(initial_state)
    except Exception as exc:
        _logger.error(
            "auto diagnosis graph failed | unit=%s | %s", summary.unit_id, exc, exc_info=True
        )
        final_state = {**initial_state, "error": str(exc)}

    record = AutoDiagnosisRecord(
        session_id=session_id,
        unit_id=summary.unit_id,
        fault_types=summary.fault_types,
        symptom_text=summary.symptom_text,
        risk_level=final_state.get("risk_level"),
        escalation_required=final_state.get("escalation_required", False),
        escalation_reason=final_state.get("escalation_reason"),
        root_causes=final_state.get("root_causes", []),
        check_steps=final_state.get("check_steps", []),
        report_draft=final_state.get("report_draft"),
        sources=final_state.get("sources", []),
        error=final_state.get("error"),
    )

    store.push(record)
    _logger.info(
        "auto diagnosis stored | unit=%s session=%s risk=%s error=%s",
        summary.unit_id,
        session_id,
        record.risk_level,
        record.error,
    )
    return record


async def run_auto_diagnosis_streaming(
    summary: FaultSummary,
    store: DiagnosisStore,
    session_id: str,
    on_phase: Callable[[str], None] | None = None,
    on_token: Callable[[str], None] | None = None,
    on_sensor_data: Callable[[list[dict]], None] | None = None,
) -> AutoDiagnosisRecord:
    """
    Auto graph version using astream_events(); callbacks update service state.

    Runs the auto-diagnosis graph (sensor_reader → symptom_parser → ... → report_gen)
    and streams phase/token updates via callbacks for live UI display.
    """
    from app.agents.graph import get_compiled_auto_graph

    auto_graph = get_compiled_auto_graph()

    fault_type = summary.fault_types[0] if summary.fault_types else "auto"
    sl = create_session_logger(
        session_id=session_id,
        unit_id=summary.unit_id,
        fault_type=fault_type,
    )
    sl.pipeline("__session__", "start",
                unit_id=summary.unit_id, fault_types=summary.fault_types)

    raw_query = (
        summary.symptom_text
        if summary.unit_id in summary.symptom_text
        else f"【{summary.unit_id}】{summary.symptom_text}"
    )

    initial_state = {
        "session_id": session_id,
        "raw_query": raw_query,
        "image_base64": None,
        "parsed_symptom": None,
        "ocr_text": None,
        "topic": None,
        "retrieved": None,
        "root_causes": [],
        "check_steps": [],
        "risk_level": "medium",
        "escalation_required": False,
        "escalation_reason": None,
        "report_draft": None,
        "stream_tokens": [],
        "sensor_reports": [r.model_dump() for r in summary.sensor_reports],
        "sensor_data": [],
        "sources": [],
        "error": None,
    }

    node_outputs: dict[str, dict] = {}
    error_str: str | None = None

    try:
        async for event in auto_graph.astream_events(initial_state, version="v2"):
            kind = event.get("event", "")
            name = event.get("name", "")

            if kind == "on_chain_start" and name in _AUTO_NODES:
                sl.pipeline(name, "start")
                if on_phase:
                    on_phase(name)

            elif kind == "on_chain_end" and name in _AUTO_NODES:
                output = (event.get("data") or {}).get("output") or {}
                if isinstance(output, dict):
                    node_outputs[name] = output
                has_error = bool(output.get("error")) if isinstance(output, dict) else False
                sl.pipeline(name, "error" if has_error else "end",
                            **({"error": output.get("error")} if has_error else {}))
                if name == "sensor_reader" and on_sensor_data:
                    on_sensor_data(output.get("sensor_data", []))

            elif kind == "on_chat_model_stream":
                chunk = (event.get("data") or {}).get("chunk")
                if chunk and getattr(chunk, "content", None):
                    if on_token:
                        on_token(chunk.content)

    except Exception as exc:
        _logger.error(
            "auto diagnosis streaming failed | unit=%s | %s",
            summary.unit_id,
            exc,
            exc_info=True,
        )
        sl.pipeline("__session__", "error", error=str(exc))
        error_str = str(exc)

    # Merge node outputs to reconstruct final state fields
    merged: dict = {}
    for node_name in ("symptom_parser", "retrieval", "reasoning", "report_gen"):
        if node_name in node_outputs:
            merged.update(node_outputs[node_name])

    record = AutoDiagnosisRecord(
        session_id=session_id,
        unit_id=summary.unit_id,
        fault_types=summary.fault_types,
        symptom_text=summary.symptom_text,
        risk_level=merged.get("risk_level", "medium"),
        escalation_required=merged.get("escalation_required", False),
        escalation_reason=merged.get("escalation_reason"),
        root_causes=merged.get("root_causes", []),
        check_steps=merged.get("check_steps", []),
        report_draft=merged.get("report_draft"),
        sources=merged.get("sources", []),
        error=error_str,
    )

    top_cause = record.root_causes[0].get("title") if record.root_causes else None
    sl.finalize(
        risk_level=record.risk_level,
        top_cause=top_cause,
        escalation_required=record.escalation_required,
        sop_steps_total=len(record.check_steps),
        error=record.error,
    )
    remove_session_logger(session_id)

    store.push(record)
    if on_phase:
        on_phase("done" if not error_str else "error")

    _logger.info(
        "auto diagnosis streaming stored | unit=%s session=%s risk=%s error=%s",
        summary.unit_id,
        session_id,
        record.risk_level,
        record.error,
    )
    return record
