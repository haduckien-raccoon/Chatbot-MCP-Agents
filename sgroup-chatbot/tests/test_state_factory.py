import unittest
import importlib
import sys
import types
from unittest.mock import AsyncMock, patch

from graph.state import build_initial_state
from services.memory_service import clear_history, save_turn


EXPECTED_KEYS = {
    "user_message",
    "session_id",
    "selected_agent",
    "selected_agents",
    "agent_queries",
    "external_data",
    "external_data_map",
    "final_response",
    "final_responses",
    "history",
}


class InitialStateFactoryTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_history("state_factory_test")

    def tearDown(self) -> None:
        clear_history("state_factory_test")
        clear_history("api_state_test")
        clear_history("mcp_state_test")

    def test_build_initial_state_returns_full_runtime_shape(self) -> None:
        save_turn("state_factory_test", "xin chao", "chao ban")

        state = build_initial_state("hoi tiep", "state_factory_test")

        self.assertEqual(set(state.keys()), EXPECTED_KEYS)
        self.assertEqual(state["user_message"], "hoi tiep")
        self.assertEqual(state["session_id"], "state_factory_test")
        self.assertEqual(state["selected_agent"], "")
        self.assertEqual(state["selected_agents"], [])
        self.assertEqual(state["agent_queries"], {})
        self.assertEqual(state["external_data"], "")
        self.assertEqual(state["external_data_map"], {})
        self.assertEqual(state["final_response"], "")
        self.assertEqual(state["final_responses"], {})
        self.assertEqual(
            state["history"],
            [
                {"role": "user", "content": "xin chao"},
                {"role": "assistant", "content": "chao ban"},
            ],
        )


class EntryPointStateTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        if "feedparser" not in sys.modules:
            sys.modules["feedparser"] = types.SimpleNamespace(
                parse=lambda _url: types.SimpleNamespace(feed={}, entries=[])
            )

    async def asyncTearDown(self) -> None:
        clear_history("api_state_test")
        clear_history("mcp_state_test")

    async def test_api_chat_uses_canonical_initial_state(self) -> None:
        api_router = importlib.import_module("api.router")
        api_schemas = importlib.import_module("api.schemas")
        captured = {}
        expected_state = build_initial_state("xin chao", "api_state_test")
        mock_result = {
            "final_response": "ok",
            "selected_agent": "general",
            "selected_agents": ["general"],
        }

        async def fake_ainvoke(state):
            captured["state"] = state
            return mock_result

        with patch("api.router.agent_graph.ainvoke", new=AsyncMock(side_effect=fake_ainvoke)):
            response = await api_router.chat(
                api_schemas.ChatRequest(message="xin chao", session_id="api_state_test")
            )

        self.assertEqual(response.reply, "ok")
        self.assertEqual(set(captured["state"].keys()), EXPECTED_KEYS)
        self.assertEqual(captured["state"], expected_state)

    async def test_mcp_chat_uses_canonical_initial_state(self) -> None:
        mcp_server = importlib.import_module("mcp_server")
        captured = {}
        expected_state = build_initial_state("xin chao", "mcp_state_test")
        mock_result = {
            "final_response": "ok",
            "selected_agent": "general",
            "selected_agents": ["general"],
        }

        async def fake_ainvoke(state):
            captured["state"] = state
            return mock_result

        with patch("mcp_server.agent_graph.ainvoke", new=AsyncMock(side_effect=fake_ainvoke)):
            response = await mcp_server.chat("xin chao", "mcp_state_test")

        self.assertEqual(response["reply"], "ok")
        self.assertEqual(set(captured["state"].keys()), EXPECTED_KEYS)
        self.assertEqual(captured["state"], expected_state)
