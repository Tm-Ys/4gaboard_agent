from typing import List, Dict, Any


class AgentMemory:
    def __init__(self):
        self.history: List[Dict[str, Any]] = []
        self.page_state: Dict[str, Any] = {}
        self.screenshots: List[str] = []

    def add_event(self, event: str, details: dict | None = None):
        entry = {"event": event, "details": details or {}}
        self.history.append(entry)

        if details and "screenshot" in details:
            self.screenshots.append(details["screenshot"])

    def get_context(self) -> str:
        parts = []
        for e in self.history[-10:]:
            event = e["event"]
            det = e.get("details", {})
            if event == "page_state":
                parts.append(
                    f"[page_state] url={det.get('url','')} "
                    f"path={det.get('path','')} "
                    f"elements={det.get('key_elements',[])}"
                )
            elif event == "click":
                parts.append(f"[click] target={det.get('target','')} method={det.get('method','')}")
            elif event == "fill":
                parts.append(f"[fill] value={det.get('value','')}")
            elif event == "navigate":
                parts.append(f"[navigate] url={det.get('url','')}")
            elif event == "wait":
                parts.append(f"[wait] seconds={det.get('seconds','')}")
            elif event == "retry":
                parts.append(f"[retry] attempt={det.get('attempt','')}")
            elif event == "step_failed":
                parts.append(f"[step_failed] target={det.get('target','')} error={det.get('error','')}")
            elif event == "recovery":
                parts.append(f"[recovery] replacement={det.get('replacement','')}")
            else:
                parts.append(f"[{event}] {str(det)[:100]}")
        return "\n".join(parts)

    def get_state_at(self, index: int) -> dict | None:
        if 0 <= index < len(self.history):
            entry = self.history[index]
            if entry["event"] == "page_state":
                return entry["details"]
        return None

    def set_page_state(self, key: str, value: Any):
        self.page_state[key] = value

    def get_page_state(self, key: str, default=None):
        return self.page_state.get(key, default)

    def get_latest_screenshot(self) -> str | None:
        return self.screenshots[-1] if self.screenshots else None

    def to_dict(self) -> dict:
        return {
            "history": self.history,
            "screenshots": self.screenshots,
            "page_state": self.page_state,
        }
