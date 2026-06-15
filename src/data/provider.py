from abc import ABC, abstractmethod

from src.types import FundamentalsResult, KlineResult


class DataProvider(ABC):
    @abstractmethod
    def get_klines(self, code: str) -> KlineResult:
        ...

    @abstractmethod
    def get_fundamentals(self, code: str) -> FundamentalsResult:
        ...
