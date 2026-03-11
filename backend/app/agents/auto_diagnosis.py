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

from app.agents.graph import get_compiled_graph
from app.store.diagnosis_store import AutoDiagnosisRecord, DiagnosisStore
from mcp_servers.fault_aggregator import FaultSummary

_logger = logging.getLogger("app.agents.auto_diagnosis")


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
