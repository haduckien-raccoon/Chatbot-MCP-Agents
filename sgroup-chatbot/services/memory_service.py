from collections import defaultdict

_sessions: dict[str, list[dict]] = defaultdict(list)
MAX_TURNS = 20


def get_history(session_id: str) -> list[dict]:
    return _sessions[session_id][-MAX_TURNS * 2 :]


def save_turn(session_id: str, user_msg: str, bot_msg: str) -> None:
    _sessions[session_id].append({"role": "user", "content": user_msg})
    _sessions[session_id].append({"role": "assistant", "content": bot_msg})


def clear_history(session_id: str) -> None:
    _sessions[session_id] = []
