"""
SSE (Server-Sent Events) utilities for streaming LangGraph output to the frontend.
"""

import json
from collections.abc import AsyncIterator


async def sse_format(event: str, data: str | dict) -> str:
    """Format a single SSE message."""
    payload = json.dumps(data, ensure_ascii=False) if isinstance(data, dict) else data
    return f"event: {event}\ndata: {payload}\n\n"


async def stream_agent_events(
    graph,
    initial_state: dict,
) -> AsyncIterator[str]:
    """
    Stream LangGraph execution events as SSE messages.

    Event types:
    - status: node transition notifications
    - token: LLM token chunks (when supported)
    - result: final DiagnosisResult JSON
    - error: error payload
    """
    try:
        async for event in graph.astream_events(initial_state, version="v2"):
            kind = event.get("event", "")
            name = event.get("name", "")

            if kind == "on_chain_start" and name in (
                "symptom_parser", "retrieval", "image_agent", "reasoning", "report_gen"
            ):
                yield await sse_format("status", {"node": name, "phase": "start"})

            elif kind == "on_chain_end" and name in (
                "symptom_parser", "retrieval", "image_agent", "reasoning", "report_gen"
            ):
                yield await sse_format("status", {"node": name, "phase": "end"})

            elif kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield await sse_format("token", {"text": chunk.content})

    except Exception as exc:
        yield await sse_format("error", {"message": str(exc)})
