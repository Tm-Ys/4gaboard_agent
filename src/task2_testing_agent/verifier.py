import json
import re
from urllib.parse import urlparse
from src.task1_scenario_generation.models import TestScenario
from .memory import AgentMemory


class Verifier:
    def _get_final_state(self, memory: AgentMemory) -> dict:
        for e in reversed(memory.history):
            if e.get("event") == "page_state":
                return e.get("details", {})
        return {}

    def _check_url_pattern(self, expectation: str, state: dict) -> bool:
        url = state.get("url", "")
        path = state.get("path", "")
        combined = f"{url} {path}"

        patterns = {
            r"项目.*页|project.*page|project.*list": "/projects/" in path,
            r"看板|board.*view|项目.*看板": "/boards/" in path or "/projects/" in path,
            r"登录.*页|login.*page": "/login" in path,
            r"首页|home.*page|dashboard": path in ("", "/"),
            r"设置|settings": "/settings" in path,
        }

        for pattern, check in patterns.items():
            if re.search(pattern, expectation, re.IGNORECASE):
                return check
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

        presence_checks = [
            (r"用户头像|user.*avatar|user.*name|已登录", "Ha" in text),
            (r"侧边栏|sidebar", "项" in text or "How" in text or "Getting started" in text),
            (r"项目.*列表|project.*list|项目名称|project.*name", "Getting started" in text),
            (r"新项目|new.*project|项目创建|created", "My" in text or "添加项目" in text),
            (r"弹窗|modal|popup|dialog", "输入项目名称" in text),
            (r"错误|error|提示|message|already.*exist|已注册", "错误" in text or "exist" in text.lower()),
            (r"卡片|card", "添加卡片" in text),
            (r"面板|board", "添加面板" in text),
            (r"列表|list", "添加列表" in text),
        ]

        for pattern, check in presence_checks:
            if re.search(pattern, expectation, re.IGNORECASE):
                return check
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

        llm = get_llm()
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
            f"你是一个测试验证专家。请判断下面的测试场景是否执行通过。\n\n"
            f"## 测试场景\n{scenario.name}\n\n"
            f"## 场景描述\n{scenario.description}\n\n"
            f"## 预期结果\n{expectations_str}\n\n"
            f"## 最终页面状态\n"
            f"URL: {state.get('url', '')}\n"
            f"Path: {state.get('path', '')}\n"
            f"可见元素: {state.get('key_elements', [])}\n\n"
            f"## 执行轨迹\n{trace}\n\n"
            f"请判断该测试是否通过。只返回 JSON 格式：\n"
            f'{{"passed": true/false, "reason": "失败原因（如果失败）"}}'
        )

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
