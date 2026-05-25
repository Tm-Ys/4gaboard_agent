import json
import os
import re
from urllib.parse import urlparse
from src.task1_scenario_generation.models import TestScenario
from .memory import AgentMemory


RULES_PATH = os.path.join(os.path.dirname(__file__), "verification_rules.json")


def _load_rules() -> dict:
    default = {
        "url_patterns": {},
        "element_presence": {},
    }
    if not os.path.exists(RULES_PATH):
        return default
    try:
        with open(RULES_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


class Verifier:
    def __init__(self):
        self.rules = _load_rules()

    def reload_rules(self):
        self.rules = _load_rules()

    def _get_final_state(self, memory: AgentMemory) -> dict:
        for e in reversed(memory.history):
            if e.get("event") == "page_state":
                return e.get("details", {})
        return {}

    def _check_url_pattern(self, expectation: str, state: dict) -> bool:
        path = state.get("path", "")
        for pattern, target_path in self.rules.get("url_patterns", {}).items():
            if re.search(pattern, expectation, re.IGNORECASE):
                return target_path in path
        return False

    def _check_text_content(self, expectation: str, state: dict) -> bool:
        text = state.get("visible_text", "")
        desc = expectation.lower()
        if desc in text.lower():
            return True
        key_elements = state.get("key_elements", [])
        for elem in key_elements:
            if elem.lower() in desc or desc in elem.lower():
                return True
        return False

    def _check_element_existence(self, expectation: str, state: dict) -> bool:
        text = state.get("visible_text", "")
        text_lower = text.lower()
        for pattern, keyword in self.rules.get("element_presence", {}).items():
            if re.search(pattern, expectation, re.IGNORECASE):
                return keyword.lower() in text_lower
        return False

    def verify(self, scenario: TestScenario, memory: AgentMemory) -> dict:
        state = self._get_final_state(memory)
        errors = []
        details = []

        for exp in scenario.expectations:
            desc = exp.description
            matched = False
            method = None

            if self._check_url_pattern(desc, state):
                matched = True
                method = "url_pattern"
            elif self._check_element_existence(desc, state):
                matched = True
                method = "element_check"
            elif self._check_text_content(desc, state):
                matched = True
                method = "text_content"
            else:
                for e in memory.history:
                    event_str = json.dumps(e, ensure_ascii=False).lower()
                    if desc.lower() in event_str:
                        matched = True
                        method = f"event:{e.get('event')}"
                        break

            details.append({
                "expectation": desc,
                "matched": matched,
                "method": method,
            })
            if not matched:
                errors.append({
                    "expectation": desc,
                    "reason": "未能在页面状态（URL、文本、元素）中找到匹配",
                })

        passed = len(errors) == 0
        return {
            "scenario": scenario.name,
            "passed": passed,
            "total_expectations": len(scenario.expectations),
            "failed_expectations": len(errors),
            "errors": errors,
            "details": details,
            "final_url": state.get("url", ""),
            "final_path": state.get("path", ""),
        }

    def verify_with_llm(self, scenario: TestScenario, memory: AgentMemory) -> dict:
        from src.task1_scenario_generation.knowledge_base import get_llm

        try:
            llm = get_llm()
            llm.request_timeout = 15
        except Exception:
            return {"scenario": scenario.name, "passed": False, "reason": "LLM init failed"}

        expectations_str = "\n".join(
            f"- {e.description}" for e in scenario.expectations
        )

        state = self._get_final_state(memory)
        trace_lines = []
        for e in memory.history:
            event = e.get("event", "")
            det = e.get("details", {})
            if event == "page_state":
                trace_lines.append(
                    f"  [page_state] url={det.get('url','')} path={det.get('path','')}"
                )
            elif det:
                trace_lines.append(f"  [{event}] {json.dumps(det, ensure_ascii=False)}")
            else:
                trace_lines.append(f"  [{event}]")

        trace = "\n".join(trace_lines)

        prompt = (
            f"You are a test verification expert. Determine if the test scenario passed.\n\n"
            f"## Scenario\n{scenario.name}\n\n"
            f"## Description\n{scenario.description}\n\n"
            f"## Expected results\n{expectations_str}\n\n"
            f"## Final page state\n"
            f"URL: {state.get('url', '')}\n"
            f"Path: {state.get('path', '')}\n"
            f"Visible elements: {state.get('key_elements', [])}\n\n"
            f"## Execution trace\n{trace}\n\n"
            f"Return only JSON: {{\"passed\": true/false, \"reason\": \"reason if failed\"}}"
        )

        try:
            response = llm.invoke(prompt)
            text = response.content.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            result = json.loads(text.strip())
            return {
                "scenario": scenario.name,
                "passed": result.get("passed", False),
                "reason": result.get("reason", ""),
            }
        except Exception:
            return {"scenario": scenario.name, "passed": False, "reason": "LLM call timed out"}
