"""
LangGraph StateGraph definition for the Hydro O&M Copilot.

Flow:
  symptom_parser
      └── (conditional route) → retrieval
                                    └── [image_agent if image present]
                                            └── reasoning
                                                    └── report_gen → END
"""

from langgraph.graph import END, StateGraph

from app.agents.image_agent import image_agent_node
from app.agents.reasoning import reasoning_node
from app.agents.report_gen import report_gen_node
from app.agents.retrieval import retrieval_node
from app.agents.state import AgentState
from app.agents.symptom_parser import symptom_parser_node


def route_after_parse(state: AgentState) -> str:
    """Route to image_agent if an image was uploaded, else go straight to retrieval."""
    if state.get("image_base64"):
        return "image_agent"
    return "retrieval"


def route_after_image(state: AgentState) -> str:
    return "retrieval"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("symptom_parser", symptom_parser_node)
    graph.add_node("image_agent", image_agent_node)
    graph.add_node("retrieval", retrieval_node)
    graph.add_node("reasoning", reasoning_node)
    graph.add_node("report_gen", report_gen_node)

    # Entry point
    graph.set_entry_point("symptom_parser")

    # Edges
    graph.add_conditional_edges(
        "symptom_parser",
        route_after_parse,
        {"image_agent": "image_agent", "retrieval": "retrieval"},
    )
    graph.add_conditional_edges(
        "image_agent",
        route_after_image,
        {"retrieval": "retrieval"},
    )
    graph.add_edge("retrieval", "reasoning")
    graph.add_edge("reasoning", "report_gen")
    graph.add_edge("report_gen", END)

    return graph


# Compiled graph (singleton, initialized at startup via lifespan)
_compiled_graph = None


def get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph().compile()
    return _compiled_graph
