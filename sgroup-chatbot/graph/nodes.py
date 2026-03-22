"""
LangGraph nodes:
orchestrate_node -> fetch_external_data_node -> generate_response_node
"""

from graph.state import AgentState
from agents.orchestrator import Orchestrator
from agents.general import GeneralAgent
from agents.ai_team import AITeamAgent
from agents.weather import WeatherAgent
from agents.news import NewsAgent
from agents.it_knowledge import ITKnowledgeAgent
from agents.sgroup_knowledge import SGroupKnowledgeAgent
from modules.registry import MODULE_REGISTRY
from services.memory_service import get_history

_orchestrator = Orchestrator()
_agents = {
    "general": GeneralAgent(),
    "ai_team": AITeamAgent(),
    "weather": WeatherAgent(),
    "news": NewsAgent(),
    "it_knowledge": ITKnowledgeAgent(),
    "sgroup_knowledge": SGroupKnowledgeAgent(),
    **{name: cls() for name, cls in MODULE_REGISTRY.items()},
}


async def orchestrate_node(state: AgentState) -> AgentState:
    """Node 1: Analyze intent and choose an agent."""
    agent_name = await _orchestrator.route(state["user_message"])
    history = get_history(state["session_id"])
    return {**state, "selected_agent": agent_name, "history": history}


async def fetch_external_data_node(state: AgentState) -> AgentState:
    """Node 2: Fetch external data if current agent needs it."""
    agent = _agents.get(state["selected_agent"])
    if agent and hasattr(agent, "fetch_data"):
        data = await agent.fetch_data(state["user_message"])
        return {**state, "external_data": data}
    return {**state, "external_data": ""}


async def generate_response_node(state: AgentState) -> AgentState:
    """Node 3: Generate final answer via selected agent + Gemini."""
    agent = _agents.get(state["selected_agent"], _agents["general"])
    response = await agent.handle(
        message=state["user_message"],
        history=state["history"],
        external_data=state.get("external_data", ""),
    )
    return {**state, "final_response": response}


def route_after_orchestrate(state: AgentState) -> str:
    """Conditional edge; all routes continue to fetch_external_data."""
    _ = state
    return "fetch_external_data"
