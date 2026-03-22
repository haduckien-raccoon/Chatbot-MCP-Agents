from mcp.server.fastmcp import FastMCP

from graph.builder import agent_graph
from graph.state import AgentState
from services.memory_service import clear_history, get_history, save_turn
from services.news_service import get_news
from services.weather_service import get_weather

mcp = FastMCP("sgroup-chatbot")


@mcp.tool()
async def chat(message: str, session_id: str = "default") -> dict:
    """Run the LangGraph chatbot pipeline and return the final response."""
    initial_state: AgentState = {
        "user_message": message,
        "session_id": session_id,
        "selected_agent": "",
        "external_data": "",
        "final_response": "",
        "history": get_history(session_id),
    }

    result = await agent_graph.ainvoke(initial_state)
    save_turn(session_id, message, result["final_response"])

    return {
        "reply": result["final_response"],
        "agent_used": result["selected_agent"],
        "session_id": session_id,
    }


@mcp.tool()
async def weather(location: str) -> dict:
    """Fetch current weather by city/location from Visual Crossing timeline API."""
    data = await get_weather(location)
    current = data.get("currentConditions") or {}

    def f_to_c(value: float | int | str | None) -> float | None:
        if value is None:
            return None
        try:
            return round((float(value) - 32) * 5 / 9, 1)
        except (TypeError, ValueError):
            return None

    def mph_to_ms(value: float | int | str | None) -> float | None:
        if value is None:
            return None
        try:
            return round(float(value) * 0.44704, 1)
        except (TypeError, ValueError):
            return None

    return {
        "location": data.get("resolvedAddress", location),
        "temperature_c": f_to_c(current.get("temp")),
        "feels_like_c": f_to_c(current.get("feelslike")),
        "humidity": current.get("humidity"),
        "wind_speed_mps": mph_to_ms(current.get("windspeed")),
        "description": current.get("conditions", ""),
        "raw": data,
    }


@mcp.tool()
async def news(query: str) -> list[dict]:
    """Search latest news and return up to 5 normalized articles."""
    articles = await get_news(query)
    normalized: list[dict] = []
    for article in articles[:5]:
        normalized.append(
            {
                "title": article.get("title", ""),
                "description": article.get("description", ""),
                "source": article.get("source", {}).get("name", ""),
                "published_at": article.get("publishedAt", ""),
                "url": article.get("url", ""),
            }
        )
    return normalized


@mcp.tool()
def clear_chat(session_id: str) -> dict:
    """Clear in-memory conversation history for a session."""
    clear_history(session_id)
    return {"status": "cleared", "session_id": session_id}


@mcp.tool()
def health() -> dict:
    """Simple health status for MCP usage."""
    return {"status": "ok", "service": "sgroup-chatbot-mcp"}


if __name__ == "__main__":
    mcp.run(transport="stdio")
