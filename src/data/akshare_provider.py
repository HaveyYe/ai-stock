from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Optional

import akshare as ak
import pandas as pd
import requests

from src.config import KLINE_PERIOD_DAYS
from src.data.provider import DataProvider
from src.types import (
    Fundamentals,
    FundamentalsResult,
    KlineResult,
    Market,
    StockSearchResult,
    StockInfo,
)
from src.utils.market_detector import detect_market, normalize_symbol

_STD_COLUMNS = ["date", "open", "close", "high", "low", "volume"]

_US_ALIAS_ROWS = [
    ("AAPL", "苹果 Apple", ["苹果", "apple", "iphone"]),
    ("MSFT", "微软 Microsoft", ["微软", "microsoft"]),
    ("NVDA", "英伟达 NVIDIA", ["英伟达", "nvidia"]),
    ("TSLA", "特斯拉 Tesla", ["特斯拉", "tesla"]),
    ("AMZN", "亚马逊 Amazon", ["亚马逊", "amazon"]),
    ("GOOGL", "谷歌 Alphabet A", ["谷歌", "google", "alphabet"]),
    ("GOOG", "谷歌 Alphabet C", ["谷歌", "google", "alphabet"]),
    ("META", "Meta", ["facebook", "脸书", "meta"]),
    ("NFLX", "奈飞 Netflix", ["奈飞", "netflix"]),
    ("BABA", "阿里巴巴 Alibaba", ["阿里巴巴", "alibaba"]),
    ("NOK", "诺基亚 Nokia", ["诺基亚", "nokia"]),
    ("BRK.A", "伯克希尔 Berkshire Hathaway A", ["伯克希尔", "berkshire"]),
    ("BRK.B", "伯克希尔 Berkshire Hathaway B", ["伯克希尔", "berkshire"]),
]

_HK_ALIAS_ROWS = [
    ("00700", "腾讯控股 Tencent", ["腾讯", "tencent"]),
    ("09988", "阿里巴巴-W Alibaba", ["阿里巴巴", "alibaba"]),
    ("03690", "美团-W Meituan", ["美团", "meituan"]),
    ("01211", "比亚迪股份 BYD", ["比亚迪", "byd"]),
    ("01810", "小米集团-W Xiaomi", ["小米", "xiaomi"]),
    ("09618", "京东集团-SW JD.com", ["京东", "jd"]),
    ("09888", "百度集团-SW Baidu", ["百度", "baidu"]),
    ("00388", "香港交易所 HKEX", ["港交所", "香港交易所", "hkex"]),
]


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


_MARKET_CN_FOR_NAME = {
    Market.A_SHARE: "A股",
    Market.HK: "港股",
    Market.US: "美股",
}


class AkShareProvider(DataProvider):
    def __init__(self, disable_proxy: bool = False):
        self._snap_cache: dict[str, _TxSnapshot] = {}
        self._resolved_name_cache: dict[str, str] = {}
        self._search_cache: Optional[list[StockSearchResult]] = None
        self._session = requests.Session()
        if disable_proxy:
            self._session.trust_env = False
            self._session.proxies = {"http": "", "https": ""}

    def _resolve_name(self, market: Market, symbol: str, snap: _TxSnapshot) -> str:
        cache_key = f"{market.value}:{symbol}"
        if cache_key in self._resolved_name_cache:
            return self._resolved_name_cache[cache_key]

        if snap.name:
            self._resolved_name_cache[cache_key] = snap.name
            return snap.name

        for item in self._static_alias_catalog():
            if item.market is market and item.symbol == symbol:
                self._resolved_name_cache[cache_key] = item.name
                return item.name

        for item in self._catalog():
            if item.market is market and item.symbol == symbol:
                self._resolved_name_cache[cache_key] = item.name
                return item.name

        fallback = f"{_MARKET_CN_FOR_NAME.get(market, market.value)} {symbol}"
        self._resolved_name_cache[cache_key] = fallback
        return fallback

    def _catalog(self) -> list[StockSearchResult]:
        if self._search_cache is None:
            rows: list[StockSearchResult] = []
            rows.extend(self._load_a_share_catalog())
            rows.extend(self._load_hk_catalog())
            rows.extend(self._load_us_catalog())
            self._search_cache = _dedupe_results(rows)
        return self._search_cache

    def _static_alias_catalog(self) -> list[StockSearchResult]:
        return _alias_results(Market.HK, _HK_ALIAS_ROWS) + _alias_results(Market.US, _US_ALIAS_ROWS)

    def _load_a_share_catalog(self) -> list[StockSearchResult]:
        try:
            df = ak.stock_info_a_code_name()
        except Exception:
            return []
        return _results_from_frame(df, Market.A_SHARE, ["code", "代码"], ["name", "名称"])

    def _load_hk_catalog(self) -> list[StockSearchResult]:
        rows = _alias_results(Market.HK, _HK_ALIAS_ROWS)
        for fn in (getattr(ak, "stock_hk_famous_spot_em", None), getattr(ak, "stock_hk_spot_em", None)):
            if fn is None:
                continue
            try:
                df = fn()
            except Exception:
                continue
            rows.extend(_results_from_frame(df, Market.HK, ["代码", "code", "f12"], ["名称", "name", "f14"]))
        return rows

    def _load_us_catalog(self) -> list[StockSearchResult]:
        rows = _alias_results(Market.US, _US_ALIAS_ROWS)
        for fn, kwargs in _us_catalog_calls():
            try:
                df = fn(**kwargs)
            except Exception:
                continue
            rows.extend(_results_from_frame(df, Market.US, ["代码", "code", "f12"], ["名称", "name", "f14"]))
        return rows

    def search_symbols(self, query: str, limit: int = 10) -> list[StockSearchResult]:
        q = query.strip()
        if not q:
            return []

        direct = _direct_code_result(q)
        if direct is not None:
            return [direct]

        q_norm = _normalize_query(q)
        static_scored = _score_catalog(q_norm, self._static_alias_catalog())
        if static_scored and static_scored[0].score >= 80:
            return static_scored[:limit]

        scored = []
        for item in self._catalog():
            score = _match_score(q_norm, item)
            if score > 0:
                scored.append(
                    StockSearchResult(
                        code=item.code,
                        symbol=item.symbol,
                        name=item.name,
                        market=item.market,
                        score=score,
                    )
                )

        return _dedupe_results(sorted(scored, key=lambda x: x.score, reverse=True))[:limit]

    def _fetch_snapshot(self, market: Market, symbol: str) -> _TxSnapshot:
        cache_key = f"{market.value}:{symbol}"
        if cache_key in self._snap_cache:
            return self._snap_cache[cache_key]

        snap = _TxSnapshot()
        try:
            tx_symbol = _tx_prefix(market, symbol) + symbol
            r = self._session.get(
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
            hint = _unknown_code_hint(code, market)
            raise RuntimeError(
                f"股票代码 {code} 无法获取行情（数据源未收录或代码格式不匹配）。{hint}"
            ) from e
        except Exception as e:
            hint = _network_hint(market)
            raise RuntimeError(
                f"获取 {code} 的行情数据失败: {type(e).__name__}: {e}。{hint}"
            ) from e

        klines = _standardize_klines(df)
        if klines.empty:
            hint = _unknown_code_hint(code, market)
            raise RuntimeError(
                f"数据源对 {code} 返回空数据，可能代码无效或数据源暂不可用。{hint}"
            )

        name = self._resolve_name(market, symbol, snap)
        info = StockInfo(code=_display_code(symbol, market), symbol=symbol, name=name, market=market)
        return KlineResult(info=info, klines=klines)

    def get_fundamentals(self, code: str) -> FundamentalsResult:
        market = detect_market(code)
        symbol = normalize_symbol(code, market)
        snap = self._fetch_snapshot(market, symbol)
        name = self._resolve_name(market, symbol, snap)
        info = StockInfo(code=_display_code(symbol, market), symbol=symbol, name=name, market=market)
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


def _network_hint(market: Market) -> str:
    source_cn = {
        Market.A_SHARE: "新浪财经 / 东方财富",
        Market.HK: "东方财富 / AKShare 港股源",
        Market.US: "东方财富 / AKShare 美股源",
    }.get(market, "数据源")
    return (
        f"若部署在海外服务器（如 Streamlit Cloud），{source_cn} 等国内行情接口可能因网络/区域限制不可达，"
        f"可稍后重试或在本地运行。"
    )


def default_provider() -> AkShareProvider:
    return AkShareProvider()


def _normalize_query(query: str) -> str:
    return query.strip().upper().replace(" ", "")


def _display_code(symbol: str, market: Market) -> str:
    if market is Market.HK:
        return symbol.zfill(5)
    return symbol.upper()


def _direct_code_result(query: str) -> Optional[StockSearchResult]:
    try:
        market = detect_market(query)
        symbol = normalize_symbol(query, market)
    except ValueError:
        return None
    return StockSearchResult(
        code=_display_code(symbol, market),
        symbol=symbol,
        name=_display_code(symbol, market),
        market=market,
        score=120.0,
    )


def _alias_results(market: Market, rows: list[tuple[str, str, list[str]]]) -> list[StockSearchResult]:
    results: list[StockSearchResult] = []
    for symbol, name, aliases in rows:
        search_name = " ".join([name, *aliases])
        results.append(
            StockSearchResult(
                code=_display_code(symbol, market),
                symbol=symbol,
                name=search_name,
                market=market,
            )
        )
    return results


def _find_col(df: pd.DataFrame, names: list[str]) -> Optional[str]:
    lower = {str(col).lower(): col for col in df.columns}
    for name in names:
        if name in df.columns:
            return name
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def _results_from_frame(
    df: pd.DataFrame,
    market: Market,
    code_cols: list[str],
    name_cols: list[str],
) -> list[StockSearchResult]:
    if df is None or df.empty:
        return []
    code_col = _find_col(df, code_cols)
    name_col = _find_col(df, name_cols)
    if code_col is None or name_col is None:
        return []

    results: list[StockSearchResult] = []
    for _, row in df.iterrows():
        raw_code = str(row.get(code_col, "")).strip()
        raw_name = str(row.get(name_col, "")).strip()
        if not raw_code or raw_code.lower() == "nan":
            continue
        symbol = _normalize_catalog_symbol(raw_code, market)
        if not symbol:
            continue
        results.append(
            StockSearchResult(
                code=_display_code(symbol, market),
                symbol=symbol,
                name=raw_name if raw_name and raw_name.lower() != "nan" else symbol,
                market=market,
            )
        )
    return results


def _normalize_catalog_symbol(raw_code: str, market: Market) -> str:
    code = raw_code.strip().upper()
    if market is Market.HK:
        digits = "".join(ch for ch in code if ch.isdigit())
        return digits.zfill(5) if digits else ""
    if market is Market.A_SHARE:
        digits = "".join(ch for ch in code if ch.isdigit())
        return digits if len(digits) == 6 else ""
    return code.replace(".US", "")


def _match_score(query: str, item: StockSearchResult) -> float:
    code = _normalize_query(item.code)
    symbol = _normalize_query(item.symbol)
    name = _normalize_query(item.name)
    if query == code or query == symbol:
        return 110.0
    if code.startswith(query) or symbol.startswith(query):
        return 95.0
    if query in name:
        return 85.0 if len(query) >= 2 else 60.0
    if query in code or query in symbol:
        return 75.0
    ratio = SequenceMatcher(None, query, name).ratio()
    if len(query) >= 3 and ratio >= 0.55:
        return 45.0 + ratio * 20.0
    return 0.0


def _score_catalog(query: str, items: list[StockSearchResult]) -> list[StockSearchResult]:
    scored: list[StockSearchResult] = []
    for item in items:
        score = _match_score(query, item)
        if score > 0:
            scored.append(
                StockSearchResult(
                    code=item.code,
                    symbol=item.symbol,
                    name=item.name,
                    market=item.market,
                    score=score,
                )
            )
    return _dedupe_results(sorted(scored, key=lambda x: x.score, reverse=True))


def _dedupe_results(items: list[StockSearchResult]) -> list[StockSearchResult]:
    seen: set[tuple[str, str]] = set()
    deduped: list[StockSearchResult] = []
    for item in items:
        key = (item.market.value, item.symbol)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _us_catalog_calls():
    spot = getattr(ak, "stock_us_spot_em", None)
    if spot is not None:
        yield spot, {}
    famous = getattr(ak, "stock_us_famous_spot_em", None)
    if famous is not None:
        for symbol in ["科技类", "金融类", "医药食品类", "媒体类", "汽车能源类", "制造零售类"]:
            yield famous, {"symbol": symbol}
