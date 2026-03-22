from typing import TypedDict

from services.memory_service import get_history


class AgentState(TypedDict):
    # Current user message
    user_message: str
    # Session id to load chat history
    session_id: str
    # Agent selected by orchestrator
    selected_agent: str
    # Multiple agents selected for a multi-intent message
    selected_agents: list[str]
    # Per-agent sub-query extracted from the user message
    agent_queries: dict[str, str]
    # Data from external APIs (weather/news/search)
    external_data: str
    # External data mapped by agent name for async multi-agent mode
    external_data_map: dict[str, str]
    # Final response returned to user
    final_response: str
    # Final responses mapped by agent name
    final_responses: dict[str, str]
    # Conversation history as list of role/content dict
    history: list[dict]


def build_initial_state(message: str, session_id: str) -> AgentState:
    """Create the canonical initial runtime state for both HTTP and MCP entrypoints."""
    return {
        "user_message": message,
        "session_id": session_id,
        "selected_agent": "",
        "selected_agents": [],
        "agent_queries": {},
        "external_data": "",
        "external_data_map": {},
        "final_response": "",
        "final_responses": {},
        "history": get_history(session_id),
    }
