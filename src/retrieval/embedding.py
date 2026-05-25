import os
import time
import requests
from typing import List, Dict
from dotenv import load_dotenv
from src.utils.log import logger
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from .base import Retriever
from .page_index import PageIndexRetriever

load_dotenv()

PERSIST_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "chroma_db")
EMBED_RETRIES = 3


class SiliconFlowEmbeddings(Embeddings):
    def __init__(self):
        self.api_key = os.getenv("TOOL_API")
        base = os.getenv("TOOL_API_URL_OPENAI", "").rstrip("/")
        if not base.endswith("/v1"):
            base += "/v1"
        self.base = base
        self.model = os.getenv("TOOL_EMBEDDING_MODEL", "BAAI/bge-m3")

    def _embed(self, texts: List[str]) -> List[List[float]]:
        resp = requests.post(
            f"{self.base}/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "input": texts},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return [item["embedding"] for item in data["data"]]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._embed(texts)

    def embed_query(self, text: str) -> List[float]:
        return self._embed([text])[0]


class EmbeddingRetriever(Retriever):
    def __init__(self):
        self._embeddings = SiliconFlowEmbeddings()
        self._store: Chroma | None = None
        self._fallback: PageIndexRetriever | None = None

    def build_index(self, pages: List[Dict[str, str]]) -> None:
        for attempt in range(EMBED_RETRIES):
            try:
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000,
                    chunk_overlap=200,
                    separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " "],
                )
                docs = []
                for page in pages:
                    chunks = splitter.split_text(page["content"])
                    for chunk in chunks:
                        doc = Document(
                            page_content=chunk,
                            metadata={"url": page["url"], "title": page["title"]},
                        )
                        docs.append(doc)
                self._store = Chroma.from_documents(
                    documents=docs,
                    embedding=self._embeddings,
                    persist_directory=PERSIST_DIR,
                )
                return
            except Exception as e:
                if attempt < EMBED_RETRIES - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.warning("Embedding build failed, using PageIndex fallback: %s", e)
                    self._build_fallback(pages)

    def _build_fallback(self, pages: List[Dict[str, str]]) -> None:
        self._fallback = PageIndexRetriever()
        self._fallback.build_index(pages)

    def _get_store(self) -> Chroma | None:
        if self._store is None:
            try:
                self._store = Chroma(
                    embedding_function=self._embeddings,
                    persist_directory=PERSIST_DIR,
                )
            except Exception:
                return None
        return self._store

    def retrieve(self, query: str, k: int = 10) -> List[Dict[str, str]]:
        for attempt in range(EMBED_RETRIES):
            try:
                store = self._get_store()
                if store is None:
                    raise RuntimeError("No vector store available")
                docs = store.similarity_search(query, k=k)
                results = [
                    {"content": d.page_content, "url": d.metadata.get("url", ""), "title": d.metadata.get("title", "")}
                    for d in docs
                ]
                reranker_model = os.getenv("TOOL_RERANKING_MODEL")
                if reranker_model:
                    results = _rerank(query, results, top_k=5)
                else:
                    results = results[:5]
                return results
            except Exception as e:
                if attempt < EMBED_RETRIES - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.warning("Embedding retrieve failed, using PageIndex fallback: %s", e)
                    if self._fallback:
                        return self._fallback.retrieve(query, k=k)
                    return []
        return []


def _rerank(query: str, documents: List[Dict[str, str]], top_k: int = 5) -> List[Dict[str, str]]:
    api_url = os.getenv("TOOL_API_URL_OPENAI", "").rstrip("/")
    api_key = os.getenv("TOOL_API")
    model = os.getenv("TOOL_RERANKING_MODEL")
    if not all([api_url, api_key, model]):
        return documents[:top_k]
    if api_url.endswith("/v1"):
        rerank_url = api_url.replace("/v1", "/v1/rerank")
    else:
        rerank_url = f"{api_url}/v1/rerank"
    try:
        resp = requests.post(
            rerank_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "query": query,
                "documents": [d["content"] for d in documents],
                "top_n": top_k,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        ordered = []
        for item in data.get("results", []):
            idx = item.get("index")
            if idx is not None and idx < len(documents):
                ordered.append(documents[idx])
        return ordered if ordered else documents[:top_k]
    except Exception as e:
        logger.warning("reranker failed: %s", e)
        return documents[:top_k]
