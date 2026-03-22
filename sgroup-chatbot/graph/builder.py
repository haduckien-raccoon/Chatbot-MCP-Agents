from langgraph.graph import END, StateGraph

from graph.nodes import (
    fetch_external_data_node,
    generate_response_node,
    orchestrate_node,
    route_after_orchestrate,
)
from graph.state import AgentState


def build_graph():
    """Build and compile LangGraph StateGraph."""
    graph = StateGraph(AgentState)

    graph.add_node("orchestrate", orchestrate_node)
    graph.add_node("fetch_external_data", fetch_external_data_node)
    graph.add_node("generate_response", generate_response_node)

    graph.set_entry_point("orchestrate")

    graph.add_conditional_edges(
        "orchestrate",
        route_after_orchestrate,
        {"fetch_external_data": "fetch_external_data"},
    )
    graph.add_edge("fetch_external_data", "generate_response")
    graph.add_edge("generate_response", END)

    return graph.compile()


agent_graph = build_graph()
