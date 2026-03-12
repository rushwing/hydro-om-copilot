"""
POST /diagnosis/run — SSE streaming diagnosis endpoint.
"""

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_graph
from app.models.request import DiagnosisRequest
from app.models.response import CheckStep, DiagnosisResult, DiagnosisTopic, RiskLevel, RootCause
from app.utils.session_log import create_session_logger, remove_session_logger
from app.utils.streaming import sse_format

router = APIRouter(prefix="/diagnosis", tags=["diagnosis"])

_NODE_NAMES = {"symptom_parser", "image_agent", "retrieval", "reasoning", "report_gen"}


@router.post("/run")
async def run_diagnosis(
    request: DiagnosisRequest,
    graph=Depends(get_graph),
) -> StreamingResponse:
    """
    Run the LangGraph diagnosis pipeline and stream results via SSE.

    The client should use EventSource or fetch + ReadableStream to consume events.
    Event types: status | token | result | error

    Single-invocation pattern: astream_events stores each node's on_chain_end
    output under its own key in `node_outputs`. The final DiagnosisResult is
    assembled by reading each field from exactly the node that owns it, so no
    node can silently overwrite another's output.
    """
    session_id = request.session_id or str(uuid.uuid4())
    sl = create_session_logger(
        session_id=session_id,
        unit_id=request.unit_id or "manual",
        fault_type="manual",
    )
    sl.pipeline("__session__", "start", query_preview=request.query[:120])

    initial_state = {
        "session_id": session_id,
        "raw_query": request.query,
        "image_base64": request.image_base64,
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

    async def event_generator():
        # Each node's on_chain_end output is stored under its own key.
        # Fields are read only from the node that owns them, so no node can
        # silently overwrite another's output.
        node_outputs: dict[str, dict] = {}

        try:
            try:
                async for event in graph.astream_events(initial_state, version="v2"):
                    kind = event.get("event", "")
                    name = event.get("name", "")

                    if kind == "on_chain_start" and name in _NODE_NAMES:
                        sl.pipeline(name, "start")
                        yield await sse_format("status", {"node": name, "phase": "start"})

                    elif kind == "on_chain_end" and name in _NODE_NAMES:
                        output = event.get("data", {}).get("output") or {}
                        if isinstance(output, dict):
                            node_outputs[name] = output
                        has_error = bool(output.get("error")) if isinstance(output, dict) else False
                        sl.pipeline(name, "error" if has_error else "end",
                                    **({"error": output.get("error")} if has_error else {}))
                        yield await sse_format("status", {"node": name, "phase": "end"})

                    elif kind == "on_chat_model_stream":
                        chunk = event.get("data", {}).get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            yield await sse_format("token", {"text": chunk.content})

            except Exception as exc:
                sl.pipeline("__session__", "error", error=str(exc))
                yield await sse_format("error", {"message": str(exc)})
                return

            # Assemble the final result from per-node outputs (explicit field ownership).
            try:
                parsed = node_outputs.get("symptom_parser", {})
                retrieval = node_outputs.get("retrieval", {})
                reasoning = node_outputs.get("reasoning", {})
                report = node_outputs.get("report_gen", {})

                raw_topic = parsed.get("topic")
                result = DiagnosisResult(
                    session_id=session_id,
                    unit_id=(parsed.get("parsed_symptom") or {}).get("unit_id"),
                    topic=DiagnosisTopic(raw_topic) if raw_topic else None,
                    root_causes=[RootCause(**rc) for rc in reasoning.get("root_causes", [])],
                    check_steps=[CheckStep(**cs) for cs in report.get("check_steps", [])],
                    risk_level=RiskLevel(reasoning.get("risk_level", "medium")),
                    escalation_required=reasoning.get("escalation_required", False),
                    escalation_reason=reasoning.get("escalation_reason"),
                    report_draft=report.get("report_draft"),
                    sources=retrieval.get("sources", []),
                )
                top_cause = result.root_causes[0].title if result.root_causes else None
                sl.finalize(
                    risk_level=result.risk_level,
                    top_cause=top_cause,
                    escalation_required=result.escalation_required,
                    sop_steps_total=len(result.check_steps),
                    fault_type=result.topic,
                )
                yield await sse_format("result", result.model_dump())
            except Exception as exc:
                sl.pipeline("__session__", "error", error=str(exc))
                yield await sse_format("error", {"message": str(exc)})
        finally:
            remove_session_logger(session_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
