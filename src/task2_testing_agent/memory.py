from typing import List, Dict, Any


class AgentMemory:
    def __init__(self):
        self.history: List[Dict[str, Any]] = []
        self.page_state: Dict[str, Any] = {}

    def add_event(self, event: str, details: dict | None = None):
        self.history.append({"event": event, "details": details or {}})

    def get_context(self) -> str:
        lines = [f"[{e['event']}]" for e in self.history[-10:]]
        return "\n".join(lines)

    def set_page_state(self, key: str, value: Any):
        self.page_state[key] = value

    def get_page_state(self, key: str, default=None):
        return self.page_state.get(key, default)
