from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

import pandas as pd


class Market(Enum):
    A_SHARE = "a_share"
    HK = "hk"
    US = "us"


@dataclass
class StockInfo:
    code: str
    symbol: str
    name: str
    market: Market


@dataclass
class StockSearchResult:
    code: str
    symbol: str
    name: str
    market: Market
    score: float = 0.0


@dataclass
class Fundamentals:
    pe_ttm: Optional[float] = None
    pb: Optional[float] = None
    roe: Optional[float] = None
    dividend_yield: Optional[float] = None
    revenue_growth: Optional[float] = None
    profit_growth: Optional[float] = None


@dataclass
class FundamentalsResult:
    info: StockInfo
    fundamentals: Fundamentals


@dataclass
class KlineResult:
    info: StockInfo
    klines: pd.DataFrame


@dataclass
class DataQuality:
    completeness: float
    kline_days: int
    latest_trade_date: Optional[str] = None
    missing_fundamentals: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
