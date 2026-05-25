import json
from typing import List
from src.task1_scenario_generation.models import TestScenario


class PlanStep:
    def __init__(self, action: str, target: str | None = None, step_type: str = "interact"):
        self.action = action
        self.target = target
        self.step_type = step_type

    def __repr__(self):
        return f"PlanStep(action={self.action}, target={self.target}, type={self.step_type})"


class Planner:
    def plan(self, scenario: TestScenario, context: str | None = None) -> List[PlanStep]:
        steps = []
        for s in scenario.steps:
            step_type = self._detect_type(s.action)
            steps.append(PlanStep(action=s.action, target=s.target, step_type=step_type))

        if context and len(steps) > 1:
            adjusted = self._adjust_with_llm(scenario, steps, context)
            if adjusted:
                return adjusted

        return steps

    def _llm_invoke_safe(self, prompt: str, timeout: int = 10):
        try:
            from langchain_core.messages import HumanMessage
            from src.task1_scenario_generation.knowledge_base import llm_invoke
            return llm_invoke([HumanMessage(content=prompt)])
        except Exception:
            return None

    def plan_recovery(self, failed_step: PlanStep, context: str) -> PlanStep | None:
        try:
            prompt = (
                f"Test step failed: {failed_step.action}(target={failed_step.target})\n"
                f"Page state:\n{context[:500]}\n\n"
                f"Suggest an alternative action. Return only JSON:\n"
                f'{{"action": "...", "target": "...", "step_type": "click|fill|navigate|wait"}}'
            )
            response = self._llm_invoke_safe(prompt)
            if not response:
                return None
            text = response.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            data = json.loads(text.strip())
            return PlanStep(
                action=data.get("action", failed_step.action),
                target=data.get("target", failed_step.target),
                step_type=data.get("step_type", "interact"),
            )
        except Exception:
            return None

    def _adjust_with_llm(self, scenario: TestScenario, steps: List[PlanStep],
                         context: str) -> List[PlanStep] | None:
        try:
            steps_json = json.dumps(
                [{"action": s.action, "target": s.target, "step_type": s.step_type} for s in steps],
                ensure_ascii=False,
            )
            prompt = (
                f"Scenario: {scenario.name}\n"
                f"Description: {scenario.description}\n"
                f"Original steps: {steps_json}\n"
                f"Page context:\n{context[:600]}\n\n"
                f"If page state suggests skipping/adjusting steps, return adjusted JSON array. "
                f"If no adjustment needed, return empty array []. "
                f"Each step: {{'action': '...', 'target': '...', 'step_type': 'click|fill|navigate|wait'}}"
            )
            response = self._llm_invoke_safe(prompt)
            if not response:
                return None
            text = response.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            data = json.loads(text.strip())
            if isinstance(data, list) and len(data) > 0:
                return [PlanStep(**item) for item in data]
        except Exception:
            pass
        return None

    def _detect_type(self, action: str) -> str:
        a = action.lower()
        if "下拉" in a or "select" in a:
            return "select"
        if any(k in a for k in ["点击", "click", "按下"]):
            return "click"
        if any(k in a for k in ["输入", "填写", "type", "fill"]):
            return "fill"
        if any(k in a for k in ["导航", "打开", "goto"]):
            return "navigate"
        if any(k in a for k in ["等待", "wait", "sleep"]):
            return "wait"
        if any(k in a for k in ["勾选", "check"]):
            return "check"
        if any(k in a for k in ["取消勾选", "uncheck"]):
            return "uncheck"
        if any(k in a for k in ["悬停", "hover"]):
            return "hover"
        if any(k in a for k in ["滚动", "scroll"]):
            return "scroll"
        if any(k in a for k in ["截图", "screenshot"]):
            return "screenshot"
        return "interact"
