import asyncio
import json
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run_test() -> None:
    project_root = Path(__file__).resolve().parent
    server_script = project_root / "mcp_server.py"

    server_params = StdioServerParameters(
        command="python3",
        args=[str(server_script)],
        cwd=str(project_root),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("\n=== MCP TOOLS ===")
            for tool in tools.tools:
                print(f"- {tool.name}")

            print("\n=== HEALTH ===")
            health_result = await session.call_tool("health", {})
            print(health_result.content[0].text)

            print("\n=== WEATHER (Da Nang) ===")
            weather_result = await session.call_tool("weather", {"location": "Da Nang"})
            print(weather_result.content[0].text)

            print("\n=== CHAT ===")
            chat_result = await session.call_tool(
                "chat",
                {
                    "message": "Xin chao, gioi thieu ngan ve SGroup va dua link chinh thuc.",
                    "session_id": "mcp_test_session",
                },
            )
            print(chat_result.content[0].text)

            print("\n=== CLEAR CHAT ===")
            clear_result = await session.call_tool(
                "clear_chat",
                {"session_id": "mcp_test_session"},
            )
            print(clear_result.content[0].text)


if __name__ == "__main__":
    try:
        asyncio.run(run_test())
    except Exception as exc:
        print("\n[MCP TEST FAILED]")
        print(str(exc))
        print("\nTip:")
        print("- Kiem tra da cai dependencies: pip install -r requirements.txt")
        print("- Kiem tra file .env co GOOGLE_API_KEY hop le")
