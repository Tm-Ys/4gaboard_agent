import os
import re
import time as time_module
import tempfile
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, Page, Browser, TimeoutError as PwTimeout
from .planner import PlanStep
from .memory import AgentMemory


class Executor:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser: Browser | None = None
        self.page: Page | None = None
        self._pw = None

    def start(self):
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(headless=self.headless)
        self.page = self.browser.new_page(viewport={"width": 800, "height": 600})
        return self

    def close(self):
        if self.browser:
            self.browser.close()
        if self._pw:
            self._pw.stop()

    def _wait_ready(self, timeout: int = 8000):
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout)
        except PwTimeout:
            pass
        for sel in [".Loader_loaderWrapper__7bP9E", ".spinner", ".loading"]:
            try:
                self.page.wait_for_selector(sel, state="hidden", timeout=3000)
            except PwTimeout:
                pass
        try:
            self.page.wait_for_selector('[class*="Sidebar"], [class*="Header"], button:has-text("添加项目")',
                                        timeout=timeout)
        except PwTimeout:
            pass

    def _wait_render(self, timeout: int = 8000):
        try:
            self.page.wait_for_selector('[class*="Header"]', timeout=timeout)
        except PwTimeout:
            pass
        try:
            self.page.wait_for_selector('[class*="Sidebar"]', timeout=timeout)
        except PwTimeout:
            pass
        import time
        time.sleep(1)

    def _wait_for_spa_navigation(self, timeout: int = 5000):
        import time as _t
        url_before = self.page.url
        _t.sleep(0.5)
        for _ in range(timeout // 200):
            _t.sleep(0.2)
            try:
                self.page.wait_for_load_state("domcontentloaded", timeout=1000)
            except Exception:
                pass
            if self.page.url != url_before:
                break

    def _locate(self, target: str):
        strategies = [
            self.page.get_by_test_id(target),
            self.page.get_by_role("button", name=target),
            self.page.get_by_role("link", name=target),
            self.page.get_by_role("textbox", name=target),
            self.page.get_by_label(target),
            self.page.get_by_placeholder(target),
            self.page.get_by_text(target, exact=False),
            self.page.locator(f'[title="{target}"]'),
            self.page.locator(f'[name="{target}"]'),
            self.page.get_by_alt_text(target),
            self.page.locator(target),
        ]
        for locator in strategies:
            try:
                if locator.count() > 0 and locator.first.is_visible(timeout=500):
                    return locator.first
            except Exception:
                continue
        return None

    def login(self, url: str = "https://demo.4gaboards.com/login") -> bool:
        email = os.environ.get("4GABOARD_ACCOUNT", "")
        password = os.environ.get("4GABOARD_PASSWORD", "")
        if not email or not password:
            raise ValueError("Missing 4GABOARD_ACCOUNT or 4GABOARD_PASSWORD in .env")

        self.page.goto(url)
        self._wait_ready()
        self.page.fill('input[name="emailOrUsername"]', email)
        self.page.fill('input[name="password"]', password)
        self.page.click('button[type="submit"]')
        self._wait_ready(15000)
        self._wait_render()
        return "login" not in self.page.url.lower()

    def navigate(self, url: str):
        if not self.page:
            raise RuntimeError("Executor not started")
        self.page.goto(url)
        self._wait_ready()

    def _parse_action(self, action: str) -> tuple[str, str]:
        a = action.lower()
        if any(k in a for k in ["点击", "click", "按下"]):
            return ("click", self._strip_prefix(action, ["点击", "按下"]))
        if any(k in a for k in ["输入", "填写", "type", "fill"]):
            return ("fill", self._strip_prefix(action, ["输入", "填写"]))
        if any(k in a for k in ["导航到", "打开", "navigate", "goto"]):
            return ("navigate", self._strip_prefix(action, ["导航到", "打开", "goto "]))
        if any(k in a for k in ["等待", "wait", "sleep"]):
            return ("wait", action)
        if any(k in a for k in ["截图", "screenshot"]):
            return ("screenshot", action)
        if any(k in a for k in ["勾选", "check"]):
            return ("check", self._strip_prefix(action, ["勾选"]))
        if any(k in a for k in ["取消勾选", "uncheck"]):
            return ("uncheck", self._strip_prefix(action, ["取消勾选"]))
        if any(k in a for k in ["悬停", "hover"]):
            return ("hover", self._strip_prefix(action, ["悬停"]))
        if any(k in a for k in ["滚动", "scroll"]):
            return ("scroll", action)
        return ("click", action)

    def _strip_prefix(self, s: str, prefixes: list[str]) -> str:
        for p in prefixes:
            if s.startswith(p):
                return s[len(p):].strip()
        return s

    def execute_step(self, step: PlanStep, memory: AgentMemory) -> bool:
        try:
            self._wait_ready()
            self._dismiss_modals()

            action_type, parsed_target = self._parse_action(step.action)
            target = step.target or parsed_target

            if action_type == "click":
                result = self._do_click(target, memory)
                self._wait_ready(3000)
            elif action_type == "fill":
                result = self._do_fill(target, step.action, memory)
            elif action_type == "navigate":
                result = self._do_navigate(target, memory)
            elif action_type == "wait":
                result = self._do_wait(target, memory)
            elif action_type == "screenshot":
                result = self._do_screenshot(memory)
            elif action_type == "check":
                result = self._do_check(target, memory)
            elif action_type == "uncheck":
                result = self._do_uncheck(target, memory)
            elif action_type == "hover":
                result = self._do_hover(target, memory)
            elif action_type == "scroll":
                result = self._do_scroll(target, memory)
            else:
                result = self._do_click(target, memory)

            self._capture_state(memory)
            return result
        except Exception as e:
            memory.add_event("step_failed", {
                "action": step.action,
                "target": step.target,
                "error": str(e),
            })
            self._capture_debug(step.action, memory)
            return False

    def _dismiss_modals(self):
        for sel in [
            'button[class*="close"]',
        ]:
            try:
                btn = self.page.locator(sel).first
                if btn.count() > 0 and btn.is_visible(timeout=200):
                    parent = self.page.locator('[class*="Sidebar"], [class*="Header"]')
                    if parent.count() > 0:
                        pass
            except Exception:
                pass

    def _click_by_text(self, text: str) -> bool:
        for tag in ["button", "a", "span", "div", "li"]:
            try:
                el = self.page.locator(f'{tag}:has-text("{text}")').first
                if el.is_visible(timeout=300):
                    el.click()
                    return True
            except Exception:
                continue
        return False

    def _do_click(self, target: str, memory: AgentMemory) -> bool:
        action_lower = (target or "").lower()

        if "提交" in action_lower or "确认" in action_lower or "确定" in action_lower:
            try:
                btn = self.page.locator('button[type="submit"]')
                if btn.is_visible(timeout=500):
                    btn.click()
                    memory.add_event("click", {"method": "submit_button", "target": target})
                    self._wait_for_spa_navigation()
                    return True
            except Exception:
                pass
            try:
                self.page.keyboard.press("Enter")
                memory.add_event("click", {"method": "submit_enter", "target": target})
                self._wait_for_spa_navigation()
                return True
            except Exception:
                pass

        if self._click_by_text(target):
            memory.add_event("click", {"method": "text_select", "target": target})
            return True
        el = self._locate(target)
        if el:
            el.click()
            memory.add_event("click", {"method": "smart_locate", "target": target})
            return True
        raise Exception(f"Cannot find clickable element: {target}")

    def _extract_value_from_action(self, action: str) -> str:
        action_lower = action.lower()
        if "输入" in action_lower or "填写" in action_lower:
            if "项目名" in action:
                return "Test Project"
            if "密码" in action:
                return os.environ.get("4GABOARD_PASSWORD", "test123")
            if "邮箱" in action or "邮件" in action:
                return os.environ.get("4GABOARD_ACCOUNT", "test@test.com")
            if "描述" in action:
                return "Test description"
            if "名称" in action:
                return "Test"
        return "test"

    def _do_fill(self, target: str, action: str, memory: AgentMemory) -> bool:
        value = target
        field_desc = self._strip_prefix(action, ["输入", "填写"])

        for sel in [
            f'input[name="{field_desc}"]',
            f'input[placeholder="{field_desc}"]',
            f'textarea[name="{field_desc}"]',
        ]:
            try:
                el = self.page.locator(sel)
                if el.is_visible(timeout=500):
                    el.fill(value)
                    memory.add_event("fill", {"selector": sel, "value": value})
                    return True
            except Exception:
                continue

        # Prefer inputs inside visible popups/modals
        for container in ['[class*="Popup"]', '[class*="Modal"]', '[role="dialog"]']:
            try:
                inputs = self.page.locator(f'{container} input, {container} textarea')
                count = inputs.count()
                for i in range(count):
                    el = inputs.nth(i)
                    if el.is_visible(timeout=200):
                        el.fill(value)
                        memory.add_event("fill", {"selector": f"{container} input", "value": value})
                        return True
            except Exception:
                continue

        for sel_type in ["input:not([type=hidden])", "textarea"]:
            try:
                el = self.page.locator(sel_type).first
                if el.is_visible(timeout=300):
                    el.fill(value)
                    memory.add_event("fill", {"selector": sel_type, "value": value})
                    return True
            except Exception:
                continue

        el = self._locate(field_desc)
        if el:
            el.fill(value)
            memory.add_event("fill", {"method": "smart_locate", "value": value})
            return True

        raise Exception(f"Cannot find input for: {field_desc}")

    def _do_navigate(self, target: str, memory: AgentMemory) -> bool:
        url = target
        if url and not url.startswith("http"):
            url = f"https://demo.4gaboards.com{url}"
        self.navigate(url or "https://demo.4gaboards.com")
        memory.add_event("navigate", {"url": self.page.url})
        return True

    def _do_wait(self, target: str, memory: AgentMemory) -> bool:
        time_match = re.search(r"(\d+)\s*秒", target)
        seconds = int(time_match.group(1)) if time_match else 2
        time_module.sleep(seconds)
        memory.add_event("wait", {"seconds": seconds})
        return True

    def _do_screenshot(self, memory: AgentMemory) -> bool:
        path = os.path.join(tempfile.gettempdir(),
                           f"screenshot_{int(time_module.time())}.png")
        self.page.screenshot(path=path)
        memory.add_event("screenshot", {"path": path})
        return True

    def _do_check(self, target: str, memory: AgentMemory) -> bool:
        if self._click_by_text(target):
            memory.add_event("check", {"target": target})
            return True
        el = self._locate(target)
        if el:
            el.check()
            return True
        raise Exception(f"Cannot find element: {target}")

    def _do_uncheck(self, target: str, memory: AgentMemory) -> bool:
        el = self._locate(target)
        if el:
            el.uncheck()
            memory.add_event("uncheck", {"target": target})
            return True
        raise Exception(f"Cannot find element: {target}")

    def _do_hover(self, target: str, memory: AgentMemory) -> bool:
        el = self._locate(target)
        if el:
            el.hover()
            memory.add_event("hover", {"target": target})
            return True
        raise Exception(f"Cannot find element: {target}")

    def _do_scroll(self, target: str, memory: AgentMemory) -> bool:
        direction = "up" if "上" in target else "down"
        delta = 300 if direction == "down" else -300
        self.page.evaluate(f"window.scrollBy(0, {delta})")
        memory.add_event("scroll", {"direction": direction})
        return True

    def _capture_state(self, memory: AgentMemory):
        try:
            import time as _time
            _time.sleep(0.5)
            url_before = self.page.url
            self._wait_ready(5000)
            _time.sleep(1)
            url = self.page.url
            parsed = urlparse(url)
            text = self.page.inner_text("body")

            key_texts = []
            for keyword in ["添加项目", "添加面板", "添加卡片", "添加列表", "Getting started",
                            "Learn 4ga Boards", "项", "看"]:
                if keyword in text:
                    key_texts.append(keyword)

            memory.add_event("page_state", {
                "title": self.page.title(),
                "url": url,
                "path": parsed.path,
                "visible_text": text[:500] if text else "",
                "key_elements": key_texts,
            })
        except Exception:
            pass

    def _capture_debug(self, label: str, memory: AgentMemory):
        try:
            timestamp = int(time_module.time())
            path = os.path.join(tempfile.gettempdir(), f"debug_{label}_{timestamp}.png")
            self.page.screenshot(path=path)
            memory.add_event("debug_capture", {
                "screenshot": path,
                "url": self.page.url,
            })
        except Exception:
            pass
