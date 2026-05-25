import json
import os
import threading
from datetime import datetime
from dotenv import load_dotenv
from src.task1_scenario_generation.models import TestScenario
from .planner import Planner, PlanStep
from .memory import AgentMemory
from .executor import Executor
from .verifier import Verifier


MAX_RETRIES = 2
REPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "testscene")
LLM_TIMEOUT = 20


def _call_with_timeout(fn, timeout: int, default):
    result = [default]
    def target():
        try:
            result[0] = fn()
        except Exception:
            pass
    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout)
    return result[0]


class TestingAgent:
    def __init__(self, headless: bool = True):
        load_dotenv()
        self.planner = Planner()
        self.executor = Executor(headless=headless)
        self.memory = AgentMemory()
        self.verifier = Verifier()

    def _precheck_scenario(self, scenario: TestScenario) -> list[str]:
        warnings = []
        for i, step in enumerate(scenario.steps):
            if not step.action:
                warnings.append(f"步骤 {i+1} 缺少 action")
            if step.action and step.target is None:
                if not any(k in step.action.lower() for k in ["等待", "wait", "sleep", "截图", "screenshot"]):
                    warnings.append(f"步骤 {i+1} 缺少 target: {step.action}")
        return warnings

    def run_scenario(
        self,
        scenario: TestScenario,
        target_url: str = "https://demo.4gaboards.com",
        auto_login: bool = True,
    ) -> dict:
        warnings = self._precheck_scenario(scenario)
        if warnings:
            self.memory.add_event("precheck_warnings", {"warnings": warnings})

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
                    "warnings": warnings,
                }
            self.memory.add_event("logged_in", {"url": self.executor.page.url})

        plan = self.planner.plan(scenario, self.memory.get_context())

        current = self.executor.page.url.rstrip("/")
        target = target_url.rstrip("/")
        if not auto_login or current != target:
            self.executor.navigate(target_url)
            self.memory.add_event("navigated", {"url": target_url})

        for plan_step in plan:
            success = self._execute_with_retry(plan_step)
            if not success:
                self.memory.add_event("plan_aborted", {
                    "step": plan_step.action,
                    "reason": "Step execution failed after retries",
                })
                break

        result = self.verifier.verify(scenario, self.memory)
        llm_result = {"scenario": scenario.name, "passed": False, "reason": "LLM skipped (API rate limited)"}

        self.executor.close()

        report = {
            "scenario": scenario.name,
            "status": "completed",
            "rule_based": result,
            "llm_based": llm_result,
            "event_count": len(self.memory.history),
            "warnings": warnings,
            "screenshots": self.memory.screenshots,
        }
        self._save_report(report)
        return report

    def _save_report(self, report: dict):
        os.makedirs(REPORT_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        name = report.get("scenario", "unknown").replace(" ", "_")
        path = os.path.join(REPORT_DIR, f"task2_report_{name}_{ts}.json")
        try:
            with open(path, "w") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _execute_with_retry(self, plan_step: PlanStep) -> bool:
        for attempt in range(1, MAX_RETRIES + 1):
            success = self.executor.execute_step(plan_step, self.memory)
            if success:
                return True
            self.memory.add_event("retry", {
                "step": plan_step.action,
                "attempt": attempt,
                "max_retries": MAX_RETRIES,
            })
        recovery_step = self.planner.plan_recovery(plan_step, self.memory.get_context())
        if recovery_step:
            self.memory.add_event("recovery", {
                "original": str(plan_step),
                "replacement": str(recovery_step),
            })
            return self.executor.execute_step(recovery_step, self.memory)
        return False
