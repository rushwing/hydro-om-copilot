"""
Shared pytest fixtures for the Hydro O&M Copilot backend test suite.

Key design decisions:
- AUTO_RANDOM_PROBLEMS_GEN=false: prevents background polling from polluting test state machines
- SENSOR_POLL_INTERVAL=999: prevents accidental sensor trigger during tests
- mock_retriever (autouse): patches app.agents.retrieval.get_retriever to a FakeRetriever
  that returns [] for all queries — this prevents loading the ~4GB embedding model
- Sync `client` fixture: kept for backward compatibility with existing tests
- Async `async_client` fixture: uses httpx.AsyncClient + ASGITransport for new async tests
"""

from __future__ import annotations

import os

# Force env vars before any app module is imported
os.environ.setdefault("AUTO_RANDOM_PROBLEMS_GEN", "false")
os.environ.setdefault("SENSOR_POLL_INTERVAL", "999")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-key-placeholder")
os.environ.setdefault("VECTOR_STORE_TYPE", "chroma")

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

# ── Fake retriever (blocks embedding model load) ──────────────────────────────


class FakeRetriever:
    """Stub retriever that returns no documents without hitting the vector store."""

    async def ainvoke(self, query: str) -> list:  # noqa: ARG002
        return []


@pytest.fixture(autouse=True)
def mock_retriever(monkeypatch):
    """Patch the retriever factory so no embedding model is loaded in any test."""
    monkeypatch.setattr(
        "app.agents.retrieval.get_retriever",
        lambda corpus: FakeRetriever(),  # noqa: ARG005
    )


# ── LangGraph stub ────────────────────────────────────────────────────────────


@pytest.fixture
def fake_graph():
    """
    Minimal LangGraph stub for integration tests.

    The stub's astream_events() immediately raises to trigger an error event.
    Tests that need a full happy-path event sequence should define their own
    mock_graph inline (see test_diagnosis.py for the pattern).
    """

    async def _noop_gen(*args, **kwargs):  # noqa: ARG001
        raise RuntimeError("fake_graph: no events configured — override in your test")
        yield  # pragma: no cover

    graph = MagicMock()
    graph.astream_events = _noop_gen
    return graph


# ── Sync client (backward compatible) ────────────────────────────────────────


@pytest.fixture
def client():
    """
    Synchronous TestClient — used by all existing tests.
    Does NOT inject fake_graph; tests that need a specific graph stub should
    set app.dependency_overrides[get_graph] directly in the test body.
    """
    from app.main import app

    return TestClient(app)


# ── Async client ──────────────────────────────────────────────────────────────


@pytest.fixture
async def async_client(fake_graph):
    """
    Async httpx client backed by ASGITransport.

    Automatically overrides get_graph with fake_graph and clears overrides
    after the test to prevent lru_cache pollution across tests.

    Usage:
        async def test_something(async_client):
            resp = await async_client.get("/health")
            assert resp.status_code == 200
    """
    from app.api.deps import get_graph
    from app.main import app

    app.dependency_overrides[get_graph] = lambda: fake_graph
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
