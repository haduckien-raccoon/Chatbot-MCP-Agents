import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import services.memory_service as memory_service


class MemoryLayersTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        memory_service._sessions.clear()
        memory_service._long_memory_cache.clear()

    def tearDown(self) -> None:
        memory_service._sessions.clear()
        memory_service._long_memory_cache.clear()
        self._tmp_dir.cleanup()

    async def test_short_memory_keeps_recent_turns(self) -> None:
        session_id = "short-memory"
        for idx in range(25):
            memory_service.save_turn(session_id, f"msg {idx}", f"reply {idx}")

        short_memory = memory_service.get_short_memory(session_id)
        self.assertEqual(len(short_memory), memory_service.MAX_SHORT_TURNS * 2)
        self.assertEqual(short_memory[0]["content"], "msg 5")
        self.assertEqual(short_memory[-1]["content"], "reply 24")

    async def test_long_memory_extracts_profile_preferences_topics(self) -> None:
        session_id = "long-memory"
        llm_output = (
            '{"profile":{"name":"An","location":"Da Nang"},'
            '"preferences":["thich python"],'
            '"topics":["python","mcp"],'
            '"memory_summary":"Nguoi dung ten An, o Da Nang, quan tam Python va MCP."}'
        )
        with patch.object(memory_service._memory_llm, "chat", new=AsyncMock(return_value=llm_output)):
            await memory_service.save_turn_with_long_memory(
                session_id,
                "toi ten la An, toi o Da Nang, toi thich python va quan tam mcp",
                "ok",
            )

        long_memory = memory_service.get_long_memory(session_id)
        self.assertEqual(long_memory["profile"].get("name"), "An")
        self.assertEqual(long_memory["profile"].get("location"), "Da Nang")
        self.assertTrue(any("python" in item.lower() for item in long_memory["preferences"]))
        self.assertIn("python", long_memory["topics"])
        self.assertIn("mcp", long_memory["topics"])

        context = memory_service.get_long_memory_context(session_id)
        self.assertIn("[LONG MEMORY]", context)
        self.assertIn("Ten nguoi dung", context)

    async def test_get_history_includes_long_memory_context(self) -> None:
        session_id = "history-memory"
        llm_output = (
            '{"profile":{"name":"Binh","location":""},'
            '"preferences":[],"topics":[],"memory_summary":"Ten nguoi dung la Binh."}'
        )
        with patch.object(memory_service._memory_llm, "chat", new=AsyncMock(return_value=llm_output)):
            await memory_service.save_turn_with_long_memory(
                session_id,
                "toi ten la Binh",
                "xin chao Binh",
            )

        history = memory_service.get_history(session_id)
        self.assertGreaterEqual(len(history), 3)
        self.assertEqual(history[0]["role"], "assistant")
        self.assertIn("[LONG MEMORY]", history[0]["content"])

    async def test_clear_history_clears_short_and_long_memory(self) -> None:
        session_id = "clear-memory"
        llm_output = (
            '{"profile":{"name":"Linh","location":""},'
            '"preferences":[],"topics":[],"memory_summary":"Ten nguoi dung la Linh."}'
        )
        with patch.object(memory_service._memory_llm, "chat", new=AsyncMock(return_value=llm_output)):
            await memory_service.save_turn_with_long_memory(session_id, "toi ten la Linh", "chao")

        memory_service.clear_history(session_id)

        self.assertEqual(memory_service.get_short_memory(session_id), [])
        self.assertEqual(memory_service.get_long_memory_context(session_id), "")


if __name__ == "__main__":
    unittest.main()
