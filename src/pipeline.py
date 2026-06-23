from dataclasses import dataclass

from src.analyzers.options_analyzer import unavailable as unavailable_options
from src.analyzers.levels import combine_support_resistance
from src.types import (
    DataQuality,
    Fundamentals,
    HoldingItem,
    KlineResult,
    OptionAnalysisResult,
    PortfolioItem,
    StockInfo,
    SupportResistanceResult,
    WatchlistAnalysisRow,
)
from src.analyzers.value_analyzer import ValueResult, analyze as analyze_value
from src.analyzers.bollinger_analyzer import BollingerResult, analyze as analyze_bollinger
from src.analyzers.fibonacci_analyzer import FibonacciResult, analyze as analyze_fibonacci
from src.analyzers.price_action_analyzer import PriceActionResult, analyze as analyze_price_action
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
    price_action_result: PriceActionResult
    option_result: OptionAnalysisResult
    level_result: SupportResistanceResult
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
    price_action_result: PriceActionResult,
    option_result: OptionAnalysisResult | None = None,
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
    for result in (value_result, bollinger_result, fibonacci_result, price_action_result):
        warnings.extend(getattr(result, "data_warnings", []) or [])
    if option_result is not None and not option_result.available:
        warnings.extend(option_result.warnings or [])
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

    matches = provider.search_symbols(raw, limit=1)
    if matches:
        return matches[0].code

    compact = raw.replace(" ", "").replace("-", "").replace("&", "")
    if compact.isalpha() and len(compact) > 5 and not raw.upper().endswith(".US"):
        raise ValueError(f"未找到匹配股票：{query}，请尝试输入更完整的代码或名称")

    try:
        market = detect_market(raw)
        return normalize_symbol(raw, market)
    except ValueError:
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
    price_action_result = analyze_price_action(klines)
    try:
        current_price = float(klines["close"].iloc[-1]) if klines is not None and not klines.empty else None
        option_result = provider.get_options_analysis(resolved_code, current_price=current_price)
    except Exception as e:
        option_result = unavailable_options(f"期权分析失败: {type(e).__name__}: {e}")

    level_result = combine_support_resistance(price_action_result, option_result, current_price=current_price)
    composite_result = compose(value_result, bollinger_result, fibonacci_result, price_action_result, option_result)
    data_quality = _build_data_quality(
        fund_result.fundamentals,
        kline_result,
        value_result,
        bollinger_result,
        fibonacci_result,
        price_action_result,
        option_result,
    )

    return AnalysisBundle(
        info=kline_result.info,
        fundamentals=fund_result.fundamentals,
        kline_result=kline_result,
        value_result=value_result,
        bollinger_result=bollinger_result,
        fibonacci_result=fibonacci_result,
        price_action_result=price_action_result,
        option_result=option_result,
        level_result=level_result,
        composite_result=composite_result,
        data_quality=data_quality,
    )


def analyze_watchlist_items(
    items: list[PortfolioItem | HoldingItem],
    provider: DataProvider = None,
) -> list[WatchlistAnalysisRow]:
    if provider is None:
        from src.data.akshare_provider import default_provider
        provider = default_provider()

    rows: list[WatchlistAnalysisRow] = []
    for item in items:
        try:
            bundle = run_analysis(item.code, provider=provider)
            klines = bundle.kline_result.klines
            latest_price = None
            change_pct = None
            if klines is not None and not klines.empty:
                latest_price = float(klines["close"].iloc[-1])
                if len(klines) >= 2:
                    previous = float(klines["close"].iloc[-2])
                    if previous:
                        change_pct = (latest_price - previous) / previous * 100

            quantity = getattr(item, "quantity", None)
            cost_price = getattr(item, "cost_price", None)
            market_value = None
            profit_loss = None
            profit_loss_pct = None
            if latest_price is not None and quantity is not None and cost_price is not None:
                market_value = latest_price * float(quantity)
                cost_value = float(cost_price) * float(quantity)
                profit_loss = market_value - cost_value
                if cost_value:
                    profit_loss_pct = profit_loss / cost_value * 100

            rows.append(
                WatchlistAnalysisRow(
                    code=bundle.info.code,
                    name=bundle.info.name,
                    market=bundle.info.market,
                    latest_price=latest_price,
                    change_pct=change_pct,
                    trade_date=bundle.data_quality.latest_trade_date,
                    action=bundle.composite_result.action,
                    score=bundle.composite_result.score,
                    support=bundle.level_result.support,
                    resistance=bundle.level_result.resistance,
                    option_label=bundle.option_result.label,
                    option_score=bundle.option_result.score if bundle.option_result.available else None,
                    quantity=quantity,
                    cost_price=cost_price,
                    market_value=market_value,
                    profit_loss=profit_loss,
                    profit_loss_pct=profit_loss_pct,
                    warnings=bundle.data_quality.warnings,
                )
            )
        except Exception as e:
            rows.append(
                WatchlistAnalysisRow(
                    code=item.code,
                    name=item.name,
                    market=item.market,
                    warnings=[f"分析失败: {type(e).__name__}: {e}"],
                )
            )
    return rows
