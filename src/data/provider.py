from abc import ABC, abstractmethod

from src.analyzers.options_analyzer import unavailable
from src.types import FundamentalsResult, KlineResult, LatestSnapshot, OptionAnalysisResult, StockSearchResult


class DataProvider(ABC):
    @abstractmethod
    def get_klines(self, code: str) -> KlineResult:
        ...

    @abstractmethod
    def get_fundamentals(self, code: str) -> FundamentalsResult:
        ...

    def search_symbols(self, query: str, limit: int = 10) -> list[StockSearchResult]:
        return []

    def get_latest_snapshot(self, code: str) -> LatestSnapshot:
        kline_result = self.get_klines(code)
        klines = kline_result.klines
        if klines is None or klines.empty:
            return LatestSnapshot(info=kline_result.info, warnings=["行情数据不可用"])

        latest = klines.iloc[-1]
        previous = klines.iloc[-2] if len(klines) >= 2 else None
        last_price = _safe_float(latest.get("close"))
        previous_close = _safe_float(previous.get("close")) if previous is not None else None
        change = None
        change_pct = None
        if last_price is not None and previous_close not in (None, 0):
            change = last_price - previous_close
            change_pct = change / previous_close * 100

        trade_date = None
        if "date" in klines.columns:
            value = latest.get("date")
            trade_date = value.strftime("%Y-%m-%d") if hasattr(value, "strftime") else str(value)

        return LatestSnapshot(
            info=kline_result.info,
            last_price=last_price,
            previous_close=previous_close,
            change=change,
            change_pct=change_pct,
            trade_date=trade_date,
        )

    def get_options_analysis(self, code: str, current_price: float | None = None) -> OptionAnalysisResult:
        return unavailable("当前数据源未提供该市场或该股票的期权链")


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
