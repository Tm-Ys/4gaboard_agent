from typing import List
from src.task1_scenario_generation.models import TestScenario


class PlanStep:
    def __init__(self, action: str, target: str | None = None):
        self.action = action
        self.target = target


class Planner:
    def plan(self, scenario: TestScenario, context: str) -> List[PlanStep]:
        steps = []
        for step in scenario.steps:
            steps.append(PlanStep(action=step.action, target=step.target))
        return steps
