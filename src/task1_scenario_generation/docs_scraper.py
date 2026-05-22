import json, os, requests, re
from bs4 import BeautifulSoup
from typing import List, Dict

DOCS_BASE = "https://docs.4gaboards.com"
CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "docs_cache", "pages.json")

PAGE_PATHS = [
    "/docs/intro", "/docs/account", "/docs/import-export",
    "/docs/structure", "/docs/project", "/docs/board",
    "/docs/board-view", "/docs/list-view", "/docs/list",
    "/docs/card", "/docs/sidebar", "/docs/notifications",
    "/docs/settings", "/docs/view", "/docs/shortcuts",
    "/docs/admin-settings", "/docs/instance-settings",
    "/docs/project-settings", "/docs/developer-manual",
]


def load_from_cache() -> List[Dict[str, str]] | None:
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def scrape_page(url: str) -> Dict[str, str]:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else ""
    for tag in soup.find_all(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article")
    content = main.get_text("\n", strip=True) if main else soup.get_text("\n", strip=True)
    content = re.sub(r"\n{3,}", "\n\n", content)
    return {"url": url, "title": title, "content": content}


def scrape_all_docs(use_cache: bool = True) -> List[Dict[str, str]]:
    if use_cache:
        cached = load_from_cache()
        if cached:
            return cached

    pages = []
    for path in PAGE_PATHS:
        url = f"{DOCS_BASE}{path}"
        try:
            pages.append(scrape_page(url))
        except Exception as e:
            print(f"Failed to scrape {url}: {e}")

    cache_dir = os.path.dirname(CACHE_PATH)
    os.makedirs(cache_dir, exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False, indent=2)

    return pages
