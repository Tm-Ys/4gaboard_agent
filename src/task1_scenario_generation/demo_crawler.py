from playwright.sync_api import sync_playwright
import os


def _login(page):
    from dotenv import load_dotenv
    load_dotenv()
    email = os.environ.get("4GABOARD_ACCOUNT", "")
    password = os.environ.get("4GABOARD_PASSWORD", "")
    if not email or not password:
        raise ValueError("Missing credentials in .env")
    page.goto("https://demo.4gaboards.com/login")
    page.wait_for_load_state("networkidle")
    page.fill('input[name="emailOrUsername"]', email)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    try:
        page.wait_for_selector('[class*="Sidebar"]', timeout=15000)
    except Exception:
        pass
    return "/login" not in page.url.lower()


def collect_ui_info(page) -> dict:
    info = {
        "buttons": [],
        "links": [],
        "inputs": [],
        "modals": {},
        "board_elements": [],
    }
    for el in page.locator("button:visible").all():
        t = el.inner_text().strip()
        if t:
            info["buttons"].append(t[:80])
    for el in page.locator("a:visible").all():
        t = el.inner_text().strip()
        if t:
            info["links"].append(t[:80])
    for el in page.locator("input:visible, textarea:visible").all():
        name = (el.get_attribute("name") or "").strip()
        pl = (el.get_attribute("placeholder") or "").strip()
        info["inputs"].append(f"name={name} placeholder={pl}")

    sidebars = page.locator('[class*="Sidebar"]')
    if sidebars.count() > 0:
        info["sidebar_text"] = sidebars.first.inner_text()[:500]

    info["current_url"] = page.url
    info["page_title"] = page.title()
    return info


def explore_demo() -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        if not _login(page):
            browser.close()
            return {"error": "Login failed"}

        result = {"dashboard": collect_ui_info(page)}

        # Click into the first project to see board view
        projects = page.locator('button:has-text("Getting started")')
        if projects.count() > 0:
            projects.first.click()
            page.wait_for_timeout(5000)
            result["project_view"] = collect_ui_info(page)

        # Click "添加项目" to see modal
        add_btn = page.locator('button:has-text("添加项目")').first
        if add_btn.count() > 0:
            add_btn.click()
            page.wait_for_timeout(1000)
            popup = page.locator('[class*="Popup"]')
            if popup.count() > 0:
                modal_info = {"text": popup.first.inner_text()[:300]}
                els = []
                for el in popup.first.locator("input, button, textarea").all():
                    tag = el.evaluate("e => e.tagName")
                    t = el.inner_text().strip()[:50]
                    name = (el.get_attribute("name") or "").strip()
                    pl = (el.get_attribute("placeholder") or "").strip()
                    els.append({"tag": tag, "text": t, "name": name, "placeholder": pl})
                modal_info["elements"] = els
                result["add_project_modal"] = modal_info

        browser.close()
        return result


SUPPORTED_ACTIONS = [
    "点击元素 (click button/link/text)",
    "输入文本 (fill input/textarea)",
    "导航到URL (navigate)",
    "等待 (wait)",
]

DEMO_UI_CACHE: dict | None = None


def get_demo_ui_context() -> str:
    global DEMO_UI_CACHE
    if DEMO_UI_CACHE is None:
        DEMO_UI_CACHE = explore_demo()
    data = DEMO_UI_CACHE
    if "error" in data:
        return f"无法登录演示站: {data['error']}"

    lines = [
        "## 演示站实际 UI 元素（仅限登录后可见）",
        "",
        "### 支持的自动化操作类型",
    ]
    for a in SUPPORTED_ACTIONS:
        lines.append(f"- {a}")

    lines.append("")
    if "dashboard" in data:
        d = data["dashboard"]
        lines.append("### 首页/仪表盘")
        lines.append(f"页面URL: {d.get('current_url', '')}")
        lines.append(f"页面标题: {d.get('page_title', '')}")
        if d.get("buttons"):
            lines.append("可见按钮:")
            for b in set(d["buttons"]):
                lines.append(f"- '{b}'")
        if d.get("inputs"):
            lines.append("可见输入框:")
            for inp in set(d["inputs"]):
                lines.append(f"- {inp}")

    if "project_view" in data:
        pv = data["project_view"]
        lines.append("")
        lines.append("### 项目页面")
        lines.append(f"页面URL: {pv.get('current_url', '')}")
        if pv.get("buttons"):
            lines.append("可见按钮:")
            for b in set(pv["buttons"]):
                lines.append(f"- '{b}'")
        if pv.get("inputs"):
            lines.append("可见输入框:")
            for inp in set(pv["inputs"]):
                lines.append(f"- {inp}")

    if "add_project_modal" in data:
        m = data["add_project_modal"]
        lines.append("")
        lines.append("### 「添加项目」弹窗")
        if m.get("text"):
            lines.append(f"弹窗内容: {m['text'][:200]}")
        if m.get("elements"):
            for el in m["elements"]:
                desc = f"<{el['tag']}>"
                if el["text"]:
                    desc += f' text="{el["text"]}"'
                if el["placeholder"]:
                    desc += f' placeholder="{el["placeholder"]}"'
                if el["name"]:
                    desc += f' name="{el["name"]}"'
                lines.append(f"- {desc}")

    lines.append("")
    lines.append("### 生成规则")
    lines.append("- action 字段必须使用文案中描述的操作意图（如'点击添加项目'），target 字段必须使用实际可见的UI元素文本")
    lines.append("- 只能使用上面列出的 UI 元素作为 target")
    lines.append("- 每个场景 2~4 步")
    lines.append("- 预期结果必须可观察（页面跳转、弹窗出现、元素内容变化等）")
    lines.append("- 不要生成涉及文件上传、拖拽、SSO/OAuth 登录注册的场景")

    return "\n".join(lines)


def clear_demo_ui_cache():
    global DEMO_UI_CACHE
    DEMO_UI_CACHE = None
