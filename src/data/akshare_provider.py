import os as _os

for _k in list(_os.environ):
    if "proxy" in _k.lower():
        del _os.environ[_k]
_os.environ["NO_PROXY"] = "*"
_os.environ["no_proxy"] = "*"

import requests as _requests

_OrigSessionInit = _requests.Session.__init__


def _no_proxy_session_init(self, *args, **kwargs):
    _OrigSessionInit(self, *args, **kwargs)
    self.trust_env = False
    self.proxies = {"http": "", "https": ""}


_requests.Session.__init__ = _no_proxy_session_init

from datetime import datetime, timedelta
from typing import Optional

import akshare as ak
import pandas as pd

from src.config import KLINE_PERIOD_DAYS
from src.data.provider import DataProvider
from src.types import (
    Fundamentals,
    FundamentalsResult,
    KlineResult,
    Market,
    StockInfo,
)
from src.utils.market_detector import detect_market, normalize_symbol

_STD_COLUMNS = ["date", "open", "close", "high", "low", "volume"]


def _date_range_dashed() -> tuple[str, str]:
    end = datetime.now()
    start = end - timedelta(days=KLINE_PERIOD_DAYS)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(f):
        return None
    return f


def _standardize_klines(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=_STD_COLUMNS)

    renamed = df.rename(columns={
        "日期": "date", "开盘": "open", "收盘": "close",
        "最高": "high", "最低": "low", "成交量": "volume",
    })

    if "date" in renamed.columns:
        renamed["date"] = pd.to_datetime(renamed["date"], errors="coerce")
        renamed = renamed.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    keep = [c for c in _STD_COLUMNS if c in renamed.columns]
    out = renamed[keep].reset_index(drop=True)
    if len(out) > KLINE_PERIOD_DAYS:
        out = out.tail(KLINE_PERIOD_DAYS).reset_index(drop=True)
    return out


def _a_share_sina_symbol(symbol: str) -> str:
    return ("sh" if symbol.startswith("6") else "sz") + symbol


def _tx_prefix(market: Market, symbol: str) -> str:
    if market is Market.A_SHARE:
        return "sh" if symbol.startswith("6") else "sz"
    if market is Market.HK:
        return "hk"
    return "us"


class _TxSnapshot:
    __slots__ = ("name", "pe_ttm", "pb", "dividend_yield", "roe")

    def __init__(self, name: str = "", pe_ttm: Optional[float] = None,
                 pb: Optional[float] = None, dividend_yield: Optional[float] = None,
                 roe: Optional[float] = None):
        self.name = name
        self.pe_ttm = pe_ttm
        self.pb = pb
        self.dividend_yield = dividend_yield
        self.roe = roe


class AkShareProvider(DataProvider):
    def __init__(self):
        self._snap_cache: dict[str, _TxSnapshot] = {}

    def _fetch_snapshot(self, market: Market, symbol: str) -> _TxSnapshot:
        cache_key = f"{market.value}:{symbol}"
        if cache_key in self._snap_cache:
            return self._snap_cache[cache_key]

        snap = _TxSnapshot()
        try:
            tx_symbol = _tx_prefix(market, symbol) + symbol
            r = _requests.get(
                f"https://qt.gtimg.cn/q={tx_symbol}",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            if r.status_code == 200 and "~" in r.text:
                parts = r.text.split("~")
                if len(parts) > 1:
                    snap.name = parts[1]
                if market is Market.A_SHARE and len(parts) > 49:
                    snap.pe_ttm = _to_float(parts[39]) if _looks_like_number(parts[39]) else None
                    snap.pb = _to_float(parts[46]) if _looks_like_number(parts[46]) else None
                    snap.dividend_yield = _to_float(parts[49]) if _looks_like_number(parts[49]) else None
                elif len(parts) > 39:
                    snap.pe_ttm = _to_float(parts[39]) if _looks_like_number(parts[39]) else None
        except Exception:
            pass

        if snap.name:
            snap.roe = self._fetch_roe(market, symbol)

        self._snap_cache[cache_key] = snap
        return snap

    @staticmethod
    def _latest_valid(df: pd.DataFrame, col: str, date_col: Optional[str] = None) -> Optional[float]:
        if df is None or df.empty or col not in df.columns:
            return None
        sub = df[df[col].notna()]
        if sub.empty:
            return None
        if date_col and date_col in sub.columns:
            try:
                sub = sub.sort_values(date_col, ascending=False)
            except Exception:
                pass
        return _to_float(sub[col].iloc[0])

    def _fetch_roe(self, market: Market, symbol: str) -> Optional[float]:
        try:
            if market is Market.A_SHARE:
                df = ak.stock_financial_analysis_indicator(symbol=symbol, start_year="2020")
                return self._latest_valid(df, "加权净资产收益率(%)", "日期")
            if market is Market.US:
                df = ak.stock_financial_us_analysis_indicator_em(symbol=symbol)
                return self._latest_valid(df, "ROE_AVG", "REPORT_DATE")
        except Exception:
            return None
        return None

    def get_klines(self, code: str) -> KlineResult:
        market = detect_market(code)
        symbol = normalize_symbol(code, market)

        snap = self._fetch_snapshot(market, symbol)
        if not snap.name:
            hint = _unknown_code_hint(code, market)
            raise RuntimeError(f"未找到股票代码 {code}，请检查是否输入正确。{hint}")

        try:
            if market is Market.A_SHARE:
                sina_symbol = _a_share_sina_symbol(symbol)
                start, end = _date_range_dashed()
                df = ak.stock_zh_a_daily(
                    symbol=sina_symbol,
                    start_date=start,
                    end_date=end,
                    adjust="qfq",
                )
            elif market is Market.HK:
                df = ak.stock_hk_daily(symbol=symbol, adjust="qfq")
            elif market is Market.US:
                try:
                    df = ak.stock_us_daily(symbol=symbol, adjust="qfq")
                    if df is None or df.empty:
                        raise ValueError("empty qfq data")
                except (ValueError, AttributeError, TypeError):
                    df = ak.stock_us_daily(symbol=symbol)
            else:
                raise ValueError(f"不支持的市场类型: {market!r}")
        except (IndexError, KeyError, ValueError) as e:
            raise RuntimeError(
                f"股票代码 {code} 无法获取行情（数据源未收录或代码格式不匹配），请确认代码正确。"
            ) from e
        except Exception as e:
            raise RuntimeError(f"获取 {code} 的行情数据失败: {e}") from e

        klines = _standardize_klines(df)
        if klines.empty:
            raise RuntimeError(f"获取 {code} 的行情数据失败: 返回空数据")

        info = StockInfo(code=code.strip().upper(), symbol=symbol, name=snap.name, market=market)
        return KlineResult(info=info, klines=klines)

    def get_fundamentals(self, code: str) -> FundamentalsResult:
        market = detect_market(code)
        symbol = normalize_symbol(code, market)
        snap = self._fetch_snapshot(market, symbol)
        info = StockInfo(code=code.strip().upper(), symbol=symbol, name=snap.name, market=market)
        fundamentals = Fundamentals(
            pe_ttm=snap.pe_ttm,
            pb=snap.pb,
            roe=snap.roe,
            dividend_yield=snap.dividend_yield,
        )
        return FundamentalsResult(info=info, fundamentals=fundamentals)


def _looks_like_number(s: str) -> bool:
    if not s:
        return False
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False


_US_TYPO_HINTS = {
    "APPLE": "苹果代码是 AAPL",
    "GOOGLE": "谷歌代码是 GOOGL（A 类）或 GOOG（C 类）",
    "MICROSOFT": "微软代码是 MSFT",
    "TESLA": "特斯拉代码是 TSLA",
    "AMAZON": "亚马逊代码是 AMZN",
    "META": "Meta 代码是 META（即原 Facebook）",
    "FACEBOOK": "Meta（原 Facebook）代码是 META",
    "NETFLIX": "奈飞代码是 NFLX",
    "NVIDIA": "英伟达代码是 NVDA",
    "BERKSHIRE": "伯克希尔代码是 BRK.A / BRK.B",
    "ALIBABA": "阿里巴巴（美股）代码是 BABA",
    "TENCENT": "腾讯是港股 00700，不是美股",
    "BYD": "比亚迪 A 股是 002594，港股是 01211",
}


def _unknown_code_hint(code: str, market: Market) -> str:
    upper = code.strip().upper()
    if market is Market.US and upper in _US_TYPO_HINTS:
        return _US_TYPO_HINTS[upper]
    if market is Market.US:
        return "美股代码通常为 1-5 个字母的缩写（如 AAPL / MSFT / NVDA）。"
    if market is Market.HK:
        return "港股代码为 5 位数字（如 00700 / 09988）。"
    if market is Market.A_SHARE:
        return "A 股代码为 6 位数字（如 600519 / 000001 / 300750）。"
    return ""


def default_provider() -> AkShareProvider:
    return AkShareProvider()
