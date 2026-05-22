from playwright.sync_api import sync_playwright, Page, Browser
from .planner import PlanStep
from .memory import AgentMemory


class Executor:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser: Browser | None = None
        self.page: Page | None = None

    def start(self):
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(headless=self.headless)
        self.page = self.browser.new_page()

    def navigate(self, url: str):
        self.page.goto(url)

    def execute_step(self, step: PlanStep, memory: AgentMemory) -> bool:
        try:
            action = step.action.lower()
            if "点击" in action or "click" in action:
                target = step.target or action
                self.page.click(f"text={target}")
            elif "输入" in action or "type" in action or "fill" in action:
                self.page.fill("input", step.target or "")
            elif "导航" in action or "goto" in action or "go to" in action:
                self.page.goto(step.target)
            else:
                self.page.keyboard.press("Enter")
            memory.add_event("step_executed", {"action": step.action})
            return True
        except Exception as e:
            memory.add_event("step_failed", {"action": step.action, "error": str(e)})
            return False

    def close(self):
        if self.browser:
            self.browser.close()
        if self._pw:
            self._pw.stop()
