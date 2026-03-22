from fastapi import APIRouter

from api.schemas import ChatRequest, ChatResponse
from graph.builder import agent_graph
from graph.state import AgentState
from services.memory_service import clear_history, get_history, save_turn

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    initial_state: AgentState = {
        "user_message": req.message,
        "session_id": req.session_id,
        "selected_agent": "",
        "selected_agents": [],
        "agent_queries": {},
        "external_data": "",
        "external_data_map": {},
        "final_response": "",
        "final_responses": {},
        "history": get_history(req.session_id),
    }

    result = await agent_graph.ainvoke(initial_state)
    save_turn(req.session_id, req.message, result["final_response"])

    selected_agents = result.get("selected_agents") or [result.get("selected_agent", "general")]
    selected_agents = [a for a in selected_agents if a]
    agent_used = ", ".join(selected_agents) if selected_agents else "general"

    return ChatResponse(
        reply=result["final_response"],
        agent_used=agent_used,
        session_id=req.session_id,
    )


@router.delete("/chat/{session_id}")
async def clear_chat(session_id: str) -> dict:
    clear_history(session_id)
    return {"status": "cleared", "session_id": session_id}


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "model": "gemini-2.5-flash"}
