"""
Integration tests for the /diagnosis/run SSE endpoint.
"""

import json
from collections import defaultdict
from unittest.mock import MagicMock

import pytest

from app.api.deps import get_graph
from app.main import app as fastapi_app


# ---------------------------------------------------------------------------
# SSE parsing helpers
# ---------------------------------------------------------------------------


class _MockChunk:
    """Minimal stand-in for an LLM streaming chunk with a .content attribute."""
    def __init__(self, content: str) -> None:
        self.content = content


def _parse_sse(body: str) -> dict[str, list[dict]]:
    """
    Parse an SSE body into {event_type: [data_dict, ...]} mapping.
    Handles multi-event streams where each event consists of
    'event: <type>' followed by 'data: <json>' lines.
    """
    events: dict[str, list] = defaultdict(list)
    current_event: str | None = None
    for line in body.splitlines():
        if line.startswith("event:"):
            current_event = line[len("event:"):].strip()
        elif line.startswith("data:") and current_event is not None:
            try:
                events[current_event].append(json.loads(line[len("data:"):].strip()))
            except json.JSONDecodeError:
                events[current_event].append(line[len("data:"):].strip())
            current_event = None
    return dict(events)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.skip(reason="Requires LLM API key and vector store — run manually")
def test_diagnosis_run_streams(client):
    with client.stream(
        "POST",
        "/diagnosis/run",
        json={"query": "#1机导叶开度异常，油压偏低"},
    ) as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]


def test_diagnosis_run_error_event(client):
    """When the graph raises an exception, the SSE stream emits an error event."""

    async def _bad_gen(*args, **kwargs):
        raise RuntimeError("LLM timeout")
        yield  # pragma: no cover — makes this an async generator

    mock_graph = MagicMock()
    mock_graph.astream_events = _bad_gen

    fastapi_app.dependency_overrides[get_graph] = lambda: mock_graph
    try:
        with client.stream(
            "POST",
            "/diagnosis/run",
            json={"query": "#1机振动异常"},
        ) as r:
            assert r.status_code == 200
            assert "text/event-stream" in r.headers["content-type"]
            body = r.read().decode("utf-8")
        assert "event: error" in body
        assert "LLM timeout" in body
    finally:
        fastapi_app.dependency_overrides.pop(get_graph, None)


def test_diagnosis_run_result_fields(client):
    """
    Normal graph completion emits all three required SSE event types
    (status, token, result) and the result payload carries the full
    DiagnosisResult fields.

    The mock generator includes on_chain_start/end (→ status events) and
    on_chat_model_stream (→ token event) so the test guards each event type
    independently, not just the final JSON payload.
    """

    async def _good_gen(*args, **kwargs):
        # status events from node lifecycle
        yield {"event": "on_chain_start", "name": "symptom_parser", "data": {}}
        yield {
            "event": "on_chain_end",
            "name": "symptom_parser",
            "data": {
                "output": {
                    "parsed_symptom": {"unit_id": "#1机"},
                    "topic": "vibration_swing",
                }
            },
        }
        yield {"event": "on_chain_start", "name": "retrieval", "data": {}}
        yield {
            "event": "on_chain_end",
            "name": "retrieval",
            "data": {"output": {"sources": []}},
        }
        yield {"event": "on_chain_start", "name": "reasoning", "data": {}}
        yield {
            "event": "on_chain_end",
            "name": "reasoning",
            "data": {
                "output": {
                    "root_causes": [
                        {
                            "rank": 1,
                            "title": "导叶开度不一致",
                            "probability": 0.85,
                            "evidence": [],
                            "parameters_to_confirm": [],
                        }
                    ],
                    "risk_level": "high",
                    "escalation_required": False,
                    "escalation_reason": None,
                }
            },
        }
        # token event from LLM streaming
        yield {
            "event": "on_chat_model_stream",
            "name": "ChatAnthropic",
            "data": {"chunk": _MockChunk("生成报告中…")},
        }
        yield {"event": "on_chain_start", "name": "report_gen", "data": {}}
        yield {
            "event": "on_chain_end",
            "name": "report_gen",
            "data": {
                "output": {
                    "check_steps": [
                        {"step": 1, "action": "检查导叶开度反馈", "expected": "开度一致", "caution": None}
                    ],
                    "report_draft": "经诊断，#1机振动异常原因为导叶开度不一致。",
                }
            },
        }

    mock_graph = MagicMock()
    mock_graph.astream_events = _good_gen

    fastapi_app.dependency_overrides[get_graph] = lambda: mock_graph
    try:
        with client.stream(
            "POST",
            "/diagnosis/run",
            json={"query": "#1机振动超标"},
        ) as r:
            assert r.status_code == 200
            body = r.read().decode("utf-8")
    finally:
        fastapi_app.dependency_overrides.pop(get_graph, None)

    events = _parse_sse(body)

    # --- status events (node lifecycle) ---
    assert "status" in events, f"No 'event: status' frames in SSE body:\n{body}"
    assert len(events["status"]) >= 2, "Expected at least start+end status frames"

    # --- token event (LLM streaming) ---
    assert "token" in events, f"No 'event: token' frames in SSE body:\n{body}"
    token_texts = [e.get("text", "") for e in events["token"]]
    assert any(t for t in token_texts), "Token event 'text' field is empty"

    # --- result event (final payload, correctly labelled) ---
    assert "result" in events, f"No 'event: result' frame in SSE body:\n{body}"
    assert len(events["result"]) == 1, "Expected exactly one result event"
    result_data = events["result"][0]
    assert "root_causes" in result_data
    assert "check_steps" in result_data
    assert "report_draft" in result_data
    assert "risk_level" in result_data
    assert result_data["risk_level"] == "high"
