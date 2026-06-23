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
class PortfolioItem:
    code: str
    symbol: str
    name: str
    market: Market
    added_at: Optional[str] = None


@dataclass
class HoldingItem:
    code: str
    symbol: str
    name: str
    market: Market
    quantity: float
    cost_price: float
    added_at: Optional[str] = None


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
class LatestSnapshot:
    info: StockInfo
    last_price: Optional[float] = None
    previous_close: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    trade_date: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class OptionAnalysisResult:
    available: bool
    score: float = 50.0
    label: str = "期权数据不可用"
    expiry: Optional[str] = None
    put_call_volume_ratio: Optional[float] = None
    put_call_open_interest_ratio: Optional[float] = None
    median_iv: Optional[float] = None
    support_strike: Optional[float] = None
    resistance_strike: Optional[float] = None
    max_put_strike: Optional[float] = None
    max_call_strike: Optional[float] = None
    signals: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    confidence: float = 0.0
    interpretation: str = ""


@dataclass
class SupportResistanceResult:
    support: Optional[float] = None
    resistance: Optional[float] = None
    support_source: str = "数据不可用"
    resistance_source: str = "数据不可用"
    signals: List[str] = field(default_factory=list)


@dataclass
class WatchlistAnalysisRow:
    code: str
    name: str
    market: Market
    latest_price: Optional[float] = None
    change_pct: Optional[float] = None
    trade_date: Optional[str] = None
    action: str = "数据不可用"
    score: Optional[float] = None
    support: Optional[float] = None
    resistance: Optional[float] = None
    option_label: str = "期权数据不可用"
    option_score: Optional[float] = None
    quantity: Optional[float] = None
    cost_price: Optional[float] = None
    market_value: Optional[float] = None
    profit_loss: Optional[float] = None
    profit_loss_pct: Optional[float] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class DataQuality:
    completeness: float
    kline_days: int
    latest_trade_date: Optional[str] = None
    missing_fundamentals: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
