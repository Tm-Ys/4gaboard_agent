import os
from .base import Retriever
from .embedding import EmbeddingRetriever
from .page_index import PageIndexRetriever

RETRIEVER_MODE_KEY = "RETRIEVER_MODE"
PAGE_INDEX = "page_index"
EMBEDDING = "embedding"


def create_retriever(mode: str | None = None) -> Retriever:
    if mode is None:
        mode = os.getenv(RETRIEVER_MODE_KEY, EMBEDDING)
    if mode == PAGE_INDEX:
        return PageIndexRetriever()
    return EmbeddingRetriever()
