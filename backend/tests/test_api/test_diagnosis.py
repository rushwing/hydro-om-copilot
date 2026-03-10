"""
Integration tests for the /diagnosis/run SSE endpoint.
"""

import pytest


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
