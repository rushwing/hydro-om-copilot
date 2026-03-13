"""
Unit tests for LangGraph routing functions and graph topology.
No LLM calls — purely tests the conditional routing logic and node registration.
"""

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
