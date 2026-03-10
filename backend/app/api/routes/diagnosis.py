"""
POST /diagnosis/run — SSE streaming diagnosis endpoint.
"""

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_graph
from app.models.request import DiagnosisRequest
from app.models.response import CheckStep, DiagnosisTopic, DiagnosisResult, RiskLevel, RootCause
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

    Single-invocation pattern: astream_events accumulates on_chain_end outputs
    per node into `accumulated`, then builds DiagnosisResult without a second
    graph.ainvoke call.
    """
    session_id = request.session_id or str(uuid.uuid4())

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
        accumulated: dict = {}

        try:
            async for event in graph.astream_events(initial_state, version="v2"):
                kind = event.get("event", "")
                name = event.get("name", "")

                if kind == "on_chain_start" and name in _NODE_NAMES:
                    yield await sse_format("status", {"node": name, "phase": "start"})

                elif kind == "on_chain_end" and name in _NODE_NAMES:
                    yield await sse_format("status", {"node": name, "phase": "end"})
                    output = event.get("data", {}).get("output") or {}
                    if isinstance(output, dict):
                        accumulated.update(output)

                elif kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        yield await sse_format("token", {"text": chunk.content})

        except Exception as exc:
            yield await sse_format("error", {"message": str(exc)})
            return

        # Build final structured result from accumulated node outputs
        try:
            merged = {**initial_state, **accumulated}
            raw_topic = merged.get("topic")
            result = DiagnosisResult(
                session_id=session_id,
                unit_id=(merged.get("parsed_symptom") or {}).get("unit_id"),
                topic=DiagnosisTopic(raw_topic) if raw_topic else None,
                root_causes=[RootCause(**rc) for rc in merged.get("root_causes", [])],
                check_steps=[CheckStep(**cs) for cs in merged.get("check_steps", [])],
                risk_level=RiskLevel(merged.get("risk_level", "medium")),
                escalation_required=merged.get("escalation_required", False),
                escalation_reason=merged.get("escalation_reason"),
                report_draft=merged.get("report_draft"),
                sources=merged.get("sources", []),
            )
            yield await sse_format("result", result.model_dump())
        except Exception as exc:
            yield await sse_format("error", {"message": str(exc)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
