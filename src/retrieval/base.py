from abc import ABC, abstractmethod
from typing import List, Dict


class Retriever(ABC):
    @abstractmethod
    def build_index(self, pages: List[Dict[str, str]]) -> None:
        ...

    @abstractmethod
    def retrieve(self, query: str, k: int = 5) -> List[Dict[str, str]]:
        ...
