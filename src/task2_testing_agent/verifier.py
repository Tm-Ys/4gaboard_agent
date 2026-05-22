from src.task1_scenario_generation.models import TestScenario
from .memory import AgentMemory


class Verifier:
    def verify(self, scenario: TestScenario, memory: AgentMemory) -> dict:
        errors = []
        for i, exp in enumerate(scenario.expectations):
            matched = any(exp.description in str(e) for e in memory.history)
            if not matched:
                errors.append({
                    "expectation": exp.description,
                    "reason": "未能在执行轨迹中找到匹配的预期状态",
                })
        passed = len(errors) == 0
        return {
            "scenario": scenario.name,
            "passed": passed,
            "total_expectations": len(scenario.expectations),
            "failed_expectations": len(errors),
            "errors": errors,
        }

    def verify_with_llm(self, scenario: TestScenario, memory: AgentMemory) -> dict:
        from src.task1_scenario_generation.knowledge_base import get_llm
        llm = get_llm()
        expectations_str = "; ".join(e.description for e in scenario.expectations)
        prompt = (
            f"测试场景：{scenario.name}\n"
            f"预期结果：{expectations_str}\n"
            f"执行轨迹：{memory.get_context()}\n"
            '请判断该测试是否通过。返回 JSON: {"passed": true/false, "reason": "失败原因"}'
        )
        response = llm.invoke(prompt)
        import json
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
