from typing import TypedDict


class AgentState(TypedDict):
    # Current user message
    user_message: str
    # Session id to load chat history
    session_id: str
    # Agent selected by orchestrator
    selected_agent: str
    # Data from external APIs (weather/news/search)
    external_data: str
    # Final response returned to user
    final_response: str
    # Conversation history as list of role/content dict
    history: list[dict]
