"""
LangGraph nodes:
orchestrate_node -> fetch_external_data_node -> generate_response_node
"""

import asyncio

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
    selected_agents, agent_queries = await _orchestrator.plan_routes(state["user_message"])
    agent_name = selected_agents[0] if selected_agents else "general"
    history = get_history(state["session_id"])
    return {
        **state,
        "selected_agent": agent_name,
        "selected_agents": selected_agents,
        "agent_queries": agent_queries,
        "history": history,
    }


async def fetch_external_data_node(state: AgentState) -> AgentState:
    """Node 2: Fetch external data if current agent needs it."""
    selected_agents = state.get("selected_agents") or [state["selected_agent"]]
    agent_queries = state.get("agent_queries", {})

    async def _fetch_for_agent(agent_name: str) -> tuple[str, str]:
        agent = _agents.get(agent_name)
        if not agent or not hasattr(agent, "fetch_data"):
            return agent_name, ""

        query = agent_queries.get(agent_name, state["user_message"])
        data = await agent.fetch_data(query)
        return agent_name, data

    results = await asyncio.gather(*[_fetch_for_agent(a) for a in selected_agents])
    external_data_map = {agent_name: data for agent_name, data in results}

    first_agent = selected_agents[0] if selected_agents else state["selected_agent"]
    return {
        **state,
        "external_data": external_data_map.get(first_agent, ""),
        "external_data_map": external_data_map,
    }


async def generate_response_node(state: AgentState) -> AgentState:
    """Node 3: Generate final answer via selected agent + Gemini."""
    selected_agents = state.get("selected_agents") or [state["selected_agent"]]
    agent_queries = state.get("agent_queries", {})
    external_data_map = state.get("external_data_map", {})

    async def _handle_for_agent(agent_name: str) -> tuple[str, str]:
        agent = _agents.get(agent_name, _agents["general"])
        query = agent_queries.get(agent_name, state["user_message"])
        response = await agent.handle(
            message=query,
            history=state["history"],
            external_data=external_data_map.get(agent_name, ""),
        )
        return agent_name, response

    results = await asyncio.gather(*[_handle_for_agent(a) for a in selected_agents])
    final_responses = {agent_name: response for agent_name, response in results}

    if len(selected_agents) == 1:
        final_response = final_responses.get(selected_agents[0], "")
        return {**state, "final_responses": final_responses, "final_response": final_response}

    agent_titles = {
        "sgroup_knowledge": "Thông tin SGroup",
        "ai_team": "Thông tin AI Team",
        "weather": "Dự báo thời tiết",
        "news": "Tin tức",
        "it_knowledge": "Kiến thức IT",
        "general": "Thông tin chung",
        "module_a": "Module A",
        "module_b": "Module B",
    }

    sections: list[str] = [
        f"Mình đã tách câu hỏi thành {len(selected_agents)} phần và xử lý song song:",
    ]
    for idx, agent_name in enumerate(selected_agents, 1):
        title = agent_titles.get(agent_name, agent_name)
        sections.append(f"\n[{idx}] {title}")
        sections.append(final_responses.get(agent_name, "Chưa có dữ liệu phù hợp."))

    return {
        **state,
        "final_responses": final_responses,
        "final_response": "\n".join(sections),
    }


def route_after_orchestrate(state: AgentState) -> str:
    """Conditional edge; all routes continue to fetch_external_data."""
    _ = state
    return "fetch_external_data"
