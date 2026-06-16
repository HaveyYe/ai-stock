from abc import ABC, abstractmethod

from src.types import FundamentalsResult, KlineResult, StockSearchResult


class DataProvider(ABC):
    @abstractmethod
    def get_klines(self, code: str) -> KlineResult:
        ...

    @abstractmethod
    def get_fundamentals(self, code: str) -> FundamentalsResult:
        ...

    def search_symbols(self, query: str, limit: int = 10) -> list[StockSearchResult]:
        return []
