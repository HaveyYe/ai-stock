from datetime import datetime, timedelta
from difflib import SequenceMatcher
import time
from typing import Optional

import akshare as ak
import pandas as pd
import requests

from src.analyzers.options_analyzer import analyze as analyze_options
from src.analyzers.options_analyzer import unavailable as unavailable_options
from src.config import KLINE_PERIOD_DAYS
from src.data.provider import DataProvider
from src.types import (
    Fundamentals,
    FundamentalsResult,
    KlineResult,
    Market,
    OptionAnalysisResult,
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
    ("INTC", "英特尔 Intel", ["英特尔", "intel"]),
    ("AMD", "超威半导体 AMD Advanced Micro Devices", ["超威", "amd", "advanced micro devices"]),
    ("ORCL", "甲骨文 Oracle", ["甲骨文", "oracle"]),
    ("IBM", "IBM International Business Machines", ["ibm", "international business machines"]),
    ("PLTR", "Palantir", ["palantir"]),
    ("COIN", "Coinbase", ["coinbase"]),
    ("AVGO", "博通 Broadcom", ["博通", "broadcom"]),
    ("QCOM", "高通 Qualcomm", ["高通", "qualcomm"]),
    ("UBER", "Uber", ["uber"]),
    ("CRM", "Salesforce", ["salesforce"]),
    ("NFLX", "奈飞 Netflix", ["奈飞", "netflix"]),
    ("BABA", "阿里巴巴 Alibaba", ["阿里巴巴", "alibaba"]),
    ("NOK", "诺基亚 Nokia", ["诺基亚", "nokia"]),
    ("SPCX", "SpaceX Space Exploration Technologies", ["spacex", "space x", "space exploration technologies"]),
    ("SPCH", "2倍做多 SPCX ETF Leverage Shares 2X Long SPCX Daily ETF", ["2x spcx", "leverage shares spcx"]),
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


def _date_range_compact() -> tuple[str, str]:
    end = datetime.now()
    start = end - timedelta(days=KLINE_PERIOD_DAYS)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


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
        self._market_search_cache: dict[Market, list[StockSearchResult]] = {}
        self._remote_search_cache: dict[str, list[StockSearchResult]] = {}
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

        if market is Market.US:
            fallback = f"{_MARKET_CN_FOR_NAME.get(market, market.value)} {symbol}"
            self._resolved_name_cache[cache_key] = fallback
            return fallback

        for item in self._market_catalog(market):
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

    def _resolve_direct_search_result(self, direct: StockSearchResult) -> StockSearchResult:
        for item in self._static_alias_catalog():
            if item.market is direct.market and item.symbol == direct.symbol:
                return StockSearchResult(
                    code=direct.code,
                    symbol=direct.symbol,
                    name=item.name,
                    market=direct.market,
                    score=direct.score,
                )

        if direct.market is Market.US:
            return direct

        for item in self._market_catalog(direct.market):
            if item.market is direct.market and item.symbol == direct.symbol:
                return StockSearchResult(
                    code=direct.code,
                    symbol=direct.symbol,
                    name=item.name,
                    market=direct.market,
                    score=direct.score,
                )
        return direct

    def _market_catalog(self, market: Market) -> list[StockSearchResult]:
        if self._search_cache is not None:
            return [item for item in self._search_cache if item.market is market]
        if market in self._market_search_cache:
            return self._market_search_cache[market]

        if market is Market.A_SHARE:
            rows = self._load_a_share_catalog()
        elif market is Market.HK:
            rows = self._load_hk_catalog()
        else:
            rows = []

        self._market_search_cache[market] = _dedupe_results(rows)
        return self._market_search_cache[market]

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

        alias = _exact_static_alias_result(q)
        if alias is not None:
            return [alias]

        q_norm = _normalize_query(q)
        static_scored = _score_catalog(q_norm, self._static_alias_catalog())
        if static_scored and static_scored[0].score >= 80:
            return static_scored[:limit]

        remote_results = self._remote_us_search(q, limit=limit) if _looks_like_english_name_query(q) else []
        if remote_results:
            return remote_results[:limit]

        direct = _direct_code_result(q)
        if direct is not None:
            return [self._resolve_direct_search_result(direct)]

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

    def _remote_us_search(self, query: str, limit: int = 10) -> list[StockSearchResult]:
        cache_key = _normalize_query(query)
        if cache_key in self._remote_search_cache:
            return self._remote_search_cache[cache_key]
        try:
            results = _fetch_yahoo_search(self._session, query, limit=limit)
        except Exception:
            results = []
        self._remote_search_cache[cache_key] = results
        return results

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

    def _fetch_us_klines(self, symbol: str) -> pd.DataFrame:
        try:
            return _fetch_yahoo_chart(self._session, symbol)
        except ValueError:
            raise
        except Exception as yahoo_error:
            errors: list[Exception] = []
            for kwargs in ({"adjust": "qfq"}, {}):
                try:
                    df = ak.stock_us_daily(symbol=symbol, **kwargs)
                    if df is not None and not df.empty:
                        return df
                except Exception as e:
                    errors.append(e)

            if errors:
                first = errors[0]
                raise RuntimeError(
                    f"Yahoo 美股源失败: {type(yahoo_error).__name__}: {yahoo_error}; "
                    f"AKShare 备用源失败: {type(first).__name__}: {first}"
                ) from first
            raise yahoo_error

    def _fetch_a_share_klines(self, symbol: str) -> pd.DataFrame:
        errors: list[Exception] = []

        try:
            start, end = _date_range_dashed()
            df = ak.stock_zh_a_daily(
                symbol=_a_share_sina_symbol(symbol),
                start_date=start,
                end_date=end,
                adjust="qfq",
            )
            if df is not None and not df.empty:
                return df
        except Exception as e:
            errors.append(e)

        try:
            start, end = _date_range_compact()
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start,
                end_date=end,
                adjust="qfq",
                timeout=10,
            )
            if df is not None and not df.empty:
                return df
            return df
        except Exception as e:
            if errors:
                first = errors[0]
                raise RuntimeError(
                    f"新浪 A股源失败: {type(first).__name__}: {first}; "
                    f"东方财富备用源失败: {type(e).__name__}: {e}"
                ) from e
            raise

    def get_klines(self, code: str) -> KlineResult:
        market = detect_market(code)
        symbol = normalize_symbol(code, market)

        snap = self._fetch_snapshot(market, symbol)

        try:
            if market is Market.A_SHARE:
                df = self._fetch_a_share_klines(symbol)
            elif market is Market.HK:
                df = ak.stock_hk_daily(symbol=symbol, adjust="qfq")
            elif market is Market.US:
                df = self._fetch_us_klines(symbol)
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

    def get_options_analysis(self, code: str, current_price: Optional[float] = None) -> OptionAnalysisResult:
        market = detect_market(code)
        symbol = normalize_symbol(code, market)
        if market is not Market.US:
            return unavailable_options("期权分析第一版仅覆盖美股个股，A 股和港股暂不参与期权评分")

        try:
            if current_price is None:
                snapshot = self.get_latest_snapshot(code)
                current_price = snapshot.last_price
            calls, puts, expiry = _fetch_yahoo_options(self._session, symbol)
            return analyze_options(calls, puts, current_price=current_price, expiry=expiry)
        except Exception as e:
            return unavailable_options(f"美股期权链获取失败: {type(e).__name__}: {e}")


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


def _yahoo_symbol(symbol: str) -> str:
    return symbol.replace(".", "-")


def _fetch_yahoo_chart(session: requests.Session, symbol: str) -> pd.DataFrame:
    yahoo_symbol = _yahoo_symbol(symbol)
    end = int(time.time())
    start = end - KLINE_PERIOD_DAYS * 2 * 86400
    response = session.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}",
        params={
            "period1": start,
            "period2": end,
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        },
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=10,
    )
    if response.status_code == 404:
        raise ValueError(f"Yahoo Finance 未收录代码 {symbol}（404 Not Found）")
    response.raise_for_status()
    payload = response.json()
    chart = payload.get("chart", {})
    error = chart.get("error")
    if error:
        description = error.get("description") if isinstance(error, dict) else str(error)
        raise ValueError(description or "Yahoo chart error")

    results = chart.get("result") or []
    if not results:
        raise ValueError("Yahoo chart returned no result")

    result = results[0]
    timestamps = result.get("timestamp") or []
    quote_rows = (result.get("indicators", {}).get("quote") or [{}])[0]
    adj_rows = result.get("indicators", {}).get("adjclose") or []
    adjclose = adj_rows[0].get("adjclose") if adj_rows else None
    close_values = adjclose or quote_rows.get("close") or []

    rows = []
    for index, ts in enumerate(timestamps):
        row = {
            "date": datetime.fromtimestamp(ts),
            "open": _nth(quote_rows.get("open"), index),
            "high": _nth(quote_rows.get("high"), index),
            "low": _nth(quote_rows.get("low"), index),
            "close": _nth(close_values, index),
            "volume": _nth(quote_rows.get("volume"), index) or 0,
        }
        if all(row[field] is not None for field in ("open", "high", "low", "close")):
            rows.append(row)

    if not rows:
        raise ValueError("Yahoo chart returned empty price rows")
    return pd.DataFrame(rows)


def _fetch_yahoo_options(session: requests.Session, symbol: str) -> tuple[pd.DataFrame, pd.DataFrame, Optional[str]]:
    yahoo_symbol = _yahoo_symbol(symbol)
    payload = _get_yahoo_options_payload(session, yahoo_symbol)
    result = _first_yahoo_option_result(payload)
    options = result.get("options") or []
    expirations = result.get("expirationDates") or []

    if not options and expirations:
        payload = _get_yahoo_options_payload(session, yahoo_symbol, expirations[0])
        result = _first_yahoo_option_result(payload)
        options = result.get("options") or []

    if not options:
        raise ValueError("Yahoo options returned no option chain")

    chain = options[0]
    expiry_ts = chain.get("expirationDate")
    expiry = datetime.fromtimestamp(expiry_ts).strftime("%Y-%m-%d") if expiry_ts else None
    calls = pd.DataFrame(chain.get("calls") or [])
    puts = pd.DataFrame(chain.get("puts") or [])
    return calls, puts, expiry


def _get_yahoo_options_payload(session: requests.Session, yahoo_symbol: str, expiry: Optional[int] = None) -> dict:
    params = {"date": expiry} if expiry is not None else None
    response = session.get(
        f"https://query2.finance.yahoo.com/v7/finance/options/{yahoo_symbol}",
        params=params,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=10,
    )
    if response.status_code == 401:
        crumb = _get_yahoo_crumb(session)
        params = dict(params or {})
        params["crumb"] = crumb
        response = session.get(
            f"https://query1.finance.yahoo.com/v7/finance/options/{yahoo_symbol}",
            params=params,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
    if response.status_code == 404:
        raise ValueError(f"Yahoo Finance 未收录 {yahoo_symbol} 的期权链")
    response.raise_for_status()
    return response.json()


def _get_yahoo_crumb(session: requests.Session) -> str:
    cached = getattr(session, "_aistock_yahoo_crumb", None)
    if cached:
        return cached
    headers = {"User-Agent": "Mozilla/5.0"}
    last_error: Optional[Exception] = None
    for attempt in range(3):
        try:
            try:
                session.get("https://fc.yahoo.com", headers=headers, timeout=6)
            except requests.RequestException:
                pass
            response = session.get(
                "https://query1.finance.yahoo.com/v1/test/getcrumb",
                headers=headers,
                timeout=8,
            )
            response.raise_for_status()
            crumb = response.text.strip()
            if crumb and not crumb.startswith("{"):
                setattr(session, "_aistock_yahoo_crumb", crumb)
                return crumb
            last_error = ValueError("Yahoo crumb is empty or invalid")
        except requests.RequestException as e:
            last_error = e
            time.sleep(0.5)
    raise ValueError(f"Yahoo crumb 获取失败: {last_error}")


def _first_yahoo_option_result(payload: dict) -> dict:
    chain = payload.get("optionChain", {})
    error = chain.get("error")
    if error:
        description = error.get("description") if isinstance(error, dict) else str(error)
        raise ValueError(description or "Yahoo option chain error")
    results = chain.get("result") or []
    if not results:
        raise ValueError("Yahoo options returned no result")
    return results[0]


def _nth(values, index: int):
    if not values or index >= len(values):
        return None
    return values[index]


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


def _looks_like_english_name_query(query: str) -> bool:
    stripped = query.strip()
    compact = stripped.replace(" ", "")
    if len(compact) < 5:
        return False
    if not any(ch.isalpha() for ch in compact):
        return False
    return all(ch.isalpha() or ch.isspace() or ch in {"&", ".", "-", "'"} for ch in stripped)


def _fetch_yahoo_search(
    session: requests.Session,
    query: str,
    limit: int = 10,
) -> list[StockSearchResult]:
    response = session.get(
        "https://query2.finance.yahoo.com/v1/finance/search",
        params={"q": query, "quotesCount": limit, "newsCount": 0},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=4,
    )
    response.raise_for_status()
    payload = response.json()
    rows: list[StockSearchResult] = []
    for item in payload.get("quotes", []) or []:
        quote_type = str(item.get("quoteType") or "").upper()
        if quote_type not in {"EQUITY", "ETF"}:
            continue
        raw_symbol = str(item.get("symbol") or "").strip().upper()
        if not raw_symbol or any(token in raw_symbol for token in ("=", "^")):
            continue
        if raw_symbol.endswith((".HK", ".SS", ".SZ")):
            continue
        symbol = raw_symbol.replace("-", ".")
        try:
            market = detect_market(symbol)
            normalized_symbol = normalize_symbol(symbol, market)
        except ValueError:
            continue
        if market is not Market.US:
            continue
        name = (
            item.get("shortname")
            or item.get("longname")
            or item.get("name")
            or normalized_symbol
        )
        rows.append(
            StockSearchResult(
                code=_display_code(normalized_symbol, market),
                symbol=normalized_symbol,
                name=str(name).strip() or normalized_symbol,
                market=market,
                score=118.0,
            )
        )
    return _dedupe_results(rows)


def _exact_static_alias_result(query: str) -> Optional[StockSearchResult]:
    q_norm = _normalize_query(query)
    for market, rows in ((Market.HK, _HK_ALIAS_ROWS), (Market.US, _US_ALIAS_ROWS)):
        for symbol, name, aliases in rows:
            candidates = [_display_code(symbol, market), symbol, *aliases]
            if q_norm in {_normalize_query(candidate) for candidate in candidates}:
                return StockSearchResult(
                    code=_display_code(symbol, market),
                    symbol=symbol,
                    name=name,
                    market=market,
                    score=125.0,
                )
    return None


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
