from typing import List, Dict
from collections import defaultdict
import re
from .base import Retriever


class PageIndexRetriever(Retriever):
    def __init__(self):
        self._pages: List[Dict[str, str]] = []
        self._keyword_index: Dict[str, List[int]] = defaultdict(list)

    def _tokenize(self, text: str) -> List[str]:
        text = text.lower()
        text = re.sub(r"[^\w\u4e00-\u9fff]+", " ", text)
        return [t for t in text.split() if len(t) > 1]

    def build_index(self, pages: List[Dict[str, str]]) -> None:
        self._pages = pages
        self._keyword_index.clear()
        for i, page in enumerate(pages):
            title = page.get("title", "")
            for token in self._tokenize(title):
                self._keyword_index[token].append(i)

    def retrieve(self, query: str, k: int = 5) -> List[Dict[str, str]]:
        query_tokens = self._tokenize(query)
        scores = defaultdict(float)
        for qt in query_tokens:
            matches = self._keyword_index.get(qt, [])
            for idx in matches:
                scores[idx] += 1.0

        title_scores = defaultdict(float)
        for i, page in enumerate(self._pages):
            title = page.get("title", "").lower()
            match_count = sum(1 for qt in query_tokens if qt in title)
            if match_count > 0:
                title_scores[i] += match_count * 2.0

        for idx, bonus in title_scores.items():
            scores[idx] += bonus

        ranked = sorted(scores.items(), key=lambda x: -x[1])
        results = []
        for idx, _ in ranked[:k]:
            page = self._pages[idx]
            results.append({
                "content": page["content"],
                "url": page.get("url", ""),
                "title": page.get("title", ""),
            })
        return results

    @property
    def pages(self) -> List[Dict[str, str]]:
        return self._pages
