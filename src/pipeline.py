from dataclasses import dataclass

from src.types import StockInfo, Fundamentals, KlineResult
from src.analyzers.value_analyzer import ValueResult, analyze as analyze_value
from src.analyzers.bollinger_analyzer import BollingerResult, analyze as analyze_bollinger
from src.analyzers.fibonacci_analyzer import FibonacciResult, analyze as analyze_fibonacci
from src.scoring.composer import CompositeResult, compose
from src.data.provider import DataProvider


@dataclass
class AnalysisBundle:
    info: StockInfo
    fundamentals: Fundamentals
    kline_result: KlineResult
    value_result: ValueResult
    bollinger_result: BollingerResult
    fibonacci_result: FibonacciResult
    composite_result: CompositeResult


def run_analysis(code: str, provider: DataProvider = None) -> AnalysisBundle:
    if provider is None:
        from src.data.akshare_provider import default_provider
        provider = default_provider()

    kline_result = provider.get_klines(code)
    fund_result = provider.get_fundamentals(code)

    klines = kline_result.klines

    value_result = analyze_value(fund_result.fundamentals)
    bollinger_result = analyze_bollinger(klines)
    fibonacci_result = analyze_fibonacci(klines)

    composite_result = compose(value_result, bollinger_result, fibonacci_result)

    return AnalysisBundle(
        info=kline_result.info,
        fundamentals=fund_result.fundamentals,
        kline_result=kline_result,
        value_result=value_result,
        bollinger_result=bollinger_result,
        fibonacci_result=fibonacci_result,
        composite_result=composite_result,
    )
