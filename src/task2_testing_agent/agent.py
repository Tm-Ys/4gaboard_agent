from dotenv import load_dotenv
from src.task1_scenario_generation.models import TestScenario
from .planner import Planner, PlanStep
from .memory import AgentMemory
from .executor import Executor
from .verifier import Verifier


class TestingAgent:
    def __init__(self, headless: bool = True):
        load_dotenv()
        self.planner = Planner()
        self.executor = Executor(headless=headless)
        self.memory = AgentMemory()
        self.verifier = Verifier()

    def run_scenario(
        self,
        scenario: TestScenario,
        target_url: str = "https://demo.4gaboards.com",
        auto_login: bool = True,
    ) -> dict:
        self.executor.start()

        if auto_login:
            self.memory.add_event("logging_in", {"url": target_url})
            login_ok = self.executor.login()
            if not login_ok:
                self.executor.close()
                return {
                    "scenario": scenario.name,
                    "status": "error",
                    "error": "Login failed",
                    "rule_based": None,
                    "llm_based": None,
                }
            self.memory.add_event("logged_in", {"url": self.executor.page.url})

        plan = self.planner.plan(scenario, self.memory.get_context())

        current = self.executor.page.url.rstrip("/")
        target = target_url.rstrip("/")
        if not auto_login or current != target:
            self.executor.navigate(target_url)
            self.memory.add_event("navigated", {"url": target_url})

        for plan_step in plan:
            success = self.executor.execute_step(plan_step, self.memory)
            if not success:
                self.memory.add_event("plan_aborted", {
                    "step": plan_step.action,
                    "reason": "Step execution failed",
                })
                break

        result = self.verifier.verify(scenario, self.memory)
        llm_result = self.verifier.verify_with_llm(scenario, self.memory)

        self.executor.close()

        return {
            "scenario": scenario.name,
            "status": "completed",
            "rule_based": result,
            "llm_based": llm_result,
            "event_count": len(self.memory.history),
        }
