"""
POST /diagnosis/run — SSE streaming diagnosis endpoint.
"""

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_graph
from app.models.request import DiagnosisRequest
from app.models.response import CheckStep, DiagnosisResult, RiskLevel, RootCause
from app.utils.streaming import sse_format, stream_agent_events

router = APIRouter(prefix="/diagnosis", tags=["diagnosis"])


@router.post("/run")
async def run_diagnosis(
    request: DiagnosisRequest,
    graph=Depends(get_graph),
) -> StreamingResponse:
    """
    Run the LangGraph diagnosis pipeline and stream results via SSE.

    The client should use EventSource or fetch + ReadableStream to consume events.
    Event types: status | token | result | error
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
        final_state = None

        async for chunk in stream_agent_events(graph, initial_state):
            yield chunk

        # After streaming completes, emit the final structured result
        # (LangGraph astream_events doesn't directly return final state;
        #  we re-invoke to get final state for the result event)
        try:
            final_state = await graph.ainvoke(initial_state)
            result = DiagnosisResult(
                session_id=session_id,
                unit_id=(final_state.get("parsed_symptom") or {}).get("unit_id"),
                topic=final_state.get("topic"),
                root_causes=[RootCause(**rc) for rc in final_state.get("root_causes", [])],
                check_steps=[CheckStep(**cs) for cs in final_state.get("check_steps", [])],
                risk_level=RiskLevel(final_state.get("risk_level", "medium")),
                escalation_required=final_state.get("escalation_required", False),
                escalation_reason=final_state.get("escalation_reason"),
                report_draft=final_state.get("report_draft"),
                sources=final_state.get("sources", []),
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
