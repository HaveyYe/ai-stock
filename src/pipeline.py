from dataclasses import dataclass

from src.types import DataQuality, Fundamentals, KlineResult, StockInfo
from src.analyzers.value_analyzer import ValueResult, analyze as analyze_value
from src.analyzers.bollinger_analyzer import BollingerResult, analyze as analyze_bollinger
from src.analyzers.fibonacci_analyzer import FibonacciResult, analyze as analyze_fibonacci
from src.scoring.composer import CompositeResult, compose
from src.data.provider import DataProvider
from src.utils.market_detector import detect_market, normalize_symbol


@dataclass
class AnalysisBundle:
    info: StockInfo
    fundamentals: Fundamentals
    kline_result: KlineResult
    value_result: ValueResult
    bollinger_result: BollingerResult
    fibonacci_result: FibonacciResult
    composite_result: CompositeResult
    data_quality: DataQuality


_FUNDAMENTAL_LABELS = {
    "pe_ttm": "PE(TTM)",
    "pb": "PB",
    "roe": "ROE",
    "dividend_yield": "股息率",
    "revenue_growth": "营收增长",
    "profit_growth": "利润增长",
}


def _build_data_quality(
    fundamentals: Fundamentals,
    kline_result: KlineResult,
    value_result: ValueResult,
    bollinger_result: BollingerResult,
    fibonacci_result: FibonacciResult,
) -> DataQuality:
    raw_fields = {
        "pe_ttm": fundamentals.pe_ttm,
        "pb": fundamentals.pb,
        "roe": fundamentals.roe,
        "dividend_yield": fundamentals.dividend_yield,
        "revenue_growth": fundamentals.revenue_growth,
        "profit_growth": fundamentals.profit_growth,
    }
    missing = [label for key, label in _FUNDAMENTAL_LABELS.items() if raw_fields.get(key) is None]
    available = len(raw_fields) - len(missing)
    fundamental_completeness = available / len(raw_fields)

    klines = kline_result.klines
    kline_days = len(klines) if klines is not None else 0
    kline_completeness = min(1.0, kline_days / 120) if kline_days else 0.0

    latest_trade_date = None
    if klines is not None and not klines.empty and "date" in klines.columns:
        latest = klines["date"].iloc[-1]
        latest_trade_date = latest.strftime("%Y-%m-%d") if hasattr(latest, "strftime") else str(latest)

    warnings = []
    for result in (value_result, bollinger_result, fibonacci_result):
        warnings.extend(getattr(result, "data_warnings", []) or [])
    if kline_days < 120:
        warnings.append("行情数据少于 120 日，长期位置判断参考性降低")

    completeness = round(fundamental_completeness * 0.55 + kline_completeness * 0.45, 2)
    return DataQuality(
        completeness=completeness,
        kline_days=kline_days,
        latest_trade_date=latest_trade_date,
        missing_fundamentals=missing,
        warnings=warnings,
    )


def _resolve_query(query: str, provider: DataProvider) -> str:
    raw = query.strip()
    if not raw:
        raise ValueError("请输入股票代码或名称")

    try:
        market = detect_market(raw)
        return normalize_symbol(raw, market)
    except ValueError:
        matches = provider.search_symbols(raw, limit=1)
        if matches:
            return matches[0].code
        raise ValueError(f"未找到匹配股票：{query}，请尝试输入更完整的代码或名称")


def run_analysis(code: str, provider: DataProvider = None) -> AnalysisBundle:
    if provider is None:
        from src.data.akshare_provider import default_provider
        provider = default_provider()

    resolved_code = _resolve_query(code, provider)
    kline_result = provider.get_klines(resolved_code)
    fund_result = provider.get_fundamentals(resolved_code)

    klines = kline_result.klines

    value_result = analyze_value(fund_result.fundamentals, kline_result.info.market)
    bollinger_result = analyze_bollinger(klines)
    fibonacci_result = analyze_fibonacci(klines)

    composite_result = compose(value_result, bollinger_result, fibonacci_result)
    data_quality = _build_data_quality(
        fund_result.fundamentals,
        kline_result,
        value_result,
        bollinger_result,
        fibonacci_result,
    )

    return AnalysisBundle(
        info=kline_result.info,
        fundamentals=fund_result.fundamentals,
        kline_result=kline_result,
        value_result=value_result,
        bollinger_result=bollinger_result,
        fibonacci_result=fibonacci_result,
        composite_result=composite_result,
        data_quality=data_quality,
    )
