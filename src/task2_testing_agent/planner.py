from typing import List, Dict
from .base import Retriever


class PlanStep:
    def __init__(self, action: str, target: str | None = None, step_type: str = "interact"):
        self.action = action
        self.target = target
        self.step_type = step_type

    def __repr__(self):
        return f"PlanStep(action={self.action}, target={self.target}, type={self.step_type})"


class Planner:
    def plan(self, scenario: "TestScenario", context: str | None = None) -> List[PlanStep]:
        from src.task1_scenario_generation.models import TestScenario
        steps = []
        for s in scenario.steps:
            step_type = self._detect_type(s.action)
            steps.append(PlanStep(action=s.action, target=s.target, step_type=step_type))
        return steps

    def _detect_type(self, action: str) -> str:
        a = action.lower()
        if any(k in a for k in ["点击", "click", "按下"]):
            return "click"
        if any(k in a for k in ["输入", "填写", "type", "fill"]):
            return "fill"
        if any(k in a for k in ["导航", "打开", "goto"]):
            return "navigate"
        if any(k in a for k in ["等待", "wait", "sleep"]):
            return "wait"
        if any(k in a for k in ["截图", "screenshot"]):
            return "screenshot"
        return "interact"
