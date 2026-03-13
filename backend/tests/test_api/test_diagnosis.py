"""
Integration tests for the /diagnosis/run SSE endpoint.
"""

import json
from unittest.mock import MagicMock

import pytest

from app.api.deps import get_graph
from app.main import app as fastapi_app


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
    """When the graph completes normally, the result event contains required DiagnosisResult fields."""

    async def _good_gen(*args, **kwargs):
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

        # Find the result event data line
        result_data = None
        for line in body.splitlines():
            if line.startswith("data:") and "root_causes" in line:
                result_data = json.loads(line[len("data:"):].strip())
                break

        assert result_data is not None, f"No result event found in SSE body:\n{body}"
        assert "root_causes" in result_data
        assert "check_steps" in result_data
        assert "report_draft" in result_data
        assert "risk_level" in result_data
        assert result_data["risk_level"] == "high"
    finally:
        fastapi_app.dependency_overrides.pop(get_graph, None)
