from fastapi import APIRouter

from api.schemas import ChatRequest, ChatResponse, LongMemoryUpsertRequest
from graph.builder import agent_graph
from graph.state import build_initial_state
from services.memory_service import (
    clear_history,
    clear_long_memory,
    get_memory_debug_info,
    get_short_memory,
    save_turn_with_long_memory,
    upsert_long_memory,
)

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    initial_state = build_initial_state(req.message, req.session_id)
    result = await agent_graph.ainvoke(initial_state)
    await save_turn_with_long_memory(req.session_id, req.message, result["final_response"])

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


@router.get("/memory/{session_id}")
async def get_memory(session_id: str) -> dict:
    short_memory = get_short_memory(session_id)
    debug_info = get_memory_debug_info(session_id)
    return {
        "session_id": session_id,
        "short_memory_turns": len(short_memory) // 2,
        "short_memory": short_memory,
        **debug_info,
    }


@router.delete("/memory/{session_id}")
async def clear_memory(session_id: str) -> dict:
    clear_long_memory(session_id)
    return {"status": "long_memory_cleared", "session_id": session_id}


@router.put("/memory/{session_id}")
async def upsert_memory(session_id: str, req: LongMemoryUpsertRequest) -> dict:
    long_memory = upsert_long_memory(session_id, req.model_dump())
    return {
        "status": "long_memory_upserted",
        "session_id": session_id,
        "long_memory": long_memory,
    }


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "model": "gemini-2.5-flash"}
