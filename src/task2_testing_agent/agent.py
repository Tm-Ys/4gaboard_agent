from src.task1_scenario_generation.models import TestScenario
from .planner import Planner
from .memory import AgentMemory
from .executor import Executor
from .verifier import Verifier
from src.retrieval.factory import create_retriever, EMBEDDING
from src.retrieval.base import Retriever


class TestingAgent:
    def __init__(self, retriever: Retriever | None = None, headless: bool = True):
        self.planner = Planner()
        self.executor = Executor(headless=headless)
        self.memory = AgentMemory()
        self.verifier = Verifier()
        self.retriever = retriever or create_retriever()

    def run_scenario(self, scenario: TestScenario, target_url: str = "https://demo.4gaboards.com") -> dict:
        plan = self.planner.plan(scenario, self.memory.get_context())

        self.executor.start()
        self.executor.navigate(target_url)
        self.memory.add_event("navigated", {"url": target_url})

        for plan_step in plan:
            success = self.executor.execute_step(plan_step, self.memory)
            if not success:
                self.memory.add_event("plan_aborted")
                break

        result = self.verifier.verify(scenario, self.memory)
        llm_result = self.verifier.verify_with_llm(scenario, self.memory)

        self.executor.close()
        return {"rule_based": result, "llm_based": llm_result}
