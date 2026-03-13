"""
Unit tests for LangGraph routing functions, graph topology, and ainvoke execution.
No LLM calls — node functions are replaced with AsyncMocks so the graph wiring
(entry point, edges, conditional routes) is exercised without any model I/O.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.graph import build_graph, route_after_image, route_after_parse


def test_route_after_parse_no_image():
    """Without an image, routing goes straight to retrieval."""
    state = {"image_base64": None}
    assert route_after_parse(state) == "retrieval"


def test_route_after_parse_no_image_missing_key():
    """Missing image_base64 key also routes to retrieval."""
    state = {}
    assert route_after_parse(state) == "retrieval"


def test_route_after_parse_with_image():
    """When image_base64 is present, routing goes through image_agent first."""
    state = {"image_base64": "aGVsbG8="}  # base64("hello")
    assert route_after_parse(state) == "image_agent"


def test_route_after_image():
    """After image_agent, routing always continues to retrieval."""
    assert route_after_image({}) == "retrieval"
    assert route_after_image({"image_base64": "abc"}) == "retrieval"


def test_graph_topology():
    """build_graph() registers exactly the expected five nodes."""
    graph = build_graph()
    compiled = graph.compile()
    node_names = set(compiled.nodes.keys())
    expected = {"symptom_parser", "image_agent", "retrieval", "reasoning", "report_gen"}
    assert expected.issubset(node_names), (
        f"Missing nodes: {expected - node_names}"
    )


# ---------------------------------------------------------------------------
# Full ainvoke execution tests (node functions mocked, no LLM)
# ---------------------------------------------------------------------------

# Minimal initial AgentState for a manual (no-image) diagnosis request.
_INITIAL_STATE = {
    "session_id": "test-ainvoke",
    "raw_query": "#1机振动超标",
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


@pytest.mark.asyncio
async def test_graph_ainvoke_no_image():
    """
    ainvoke() executes the 4-node no-image path end-to-end and returns a
    merged AgentState that contains root_causes, check_steps, and report_draft.

    All five node functions are replaced with AsyncMocks *before* build_graph()
    is called so the mocks are what LangGraph registers and executes.  This
    exercises the real entry point, edge wiring (symptom_parser → retrieval →
    reasoning → report_gen), and state-merge semantics without any LLM calls.
    """
    mock_symptom_parser = AsyncMock(return_value={
        "parsed_symptom": {"unit_id": "#1机"},
        "topic": "vibration_swing",
    })
    mock_retrieval = AsyncMock(return_value={"sources": ["VIB.001"]})
    mock_reasoning = AsyncMock(return_value={
        "root_causes": [
            {"rank": 1, "title": "转轮质量不平衡", "probability": 0.9,
             "evidence": [], "parameters_to_confirm": []},
        ],
        "risk_level": "high",
        "escalation_required": False,
        "escalation_reason": None,
    })
    mock_report_gen = AsyncMock(return_value={
        "check_steps": [{"step": 1, "action": "检查导叶开度", "expected": None, "caution": None}],
        "report_draft": "诊断报告草稿",
    })
    mock_image_agent = AsyncMock(return_value={})  # not on this path

    with (
        patch("app.agents.graph.symptom_parser_node", mock_symptom_parser),
        patch("app.agents.graph.retrieval_node", mock_retrieval),
        patch("app.agents.graph.reasoning_node", mock_reasoning),
        patch("app.agents.graph.report_gen_node", mock_report_gen),
        patch("app.agents.graph.image_agent_node", mock_image_agent),
    ):
        compiled = build_graph().compile()
        result = await compiled.ainvoke(_INITIAL_STATE)

    # Verify the merged state has the full AgentState contract fields
    assert "root_causes" in result
    assert "check_steps" in result
    assert "report_draft" in result
    assert result["risk_level"] == "high"
    assert result["report_draft"] == "诊断报告草稿"

    # Verify only the expected nodes were called (image_agent must be skipped)
    mock_symptom_parser.assert_called_once()
    mock_retrieval.assert_called_once()
    mock_reasoning.assert_called_once()
    mock_report_gen.assert_called_once()
    mock_image_agent.assert_not_called()
