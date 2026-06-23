import unittest
from datetime import datetime, timedelta

import pandas as pd

from src.data.provider import DataProvider
from src.pipeline import AnalysisBundle, analyze_watchlist_items, run_analysis
from src.types import (
    Fundamentals,
    FundamentalsResult,
    HoldingItem,
    KlineResult,
    Market,
    PortfolioItem,
    StockSearchResult,
    StockInfo,
)


def _make_klines(n: int = 30) -> pd.DataFrame:
    rows = []
    for i in range(n):
        base = 100.0 + (1.0 if i % 2 == 0 else -1.0)
        rows.append(
            {
                "date": datetime(2024, 1, 1) + timedelta(days=i),
                "open": base,
                "close": base + 0.5,
                "high": base + 1.5,
                "low": base - 1.0,
                "volume": 1000 + i * 10,
            }
        )
    return pd.DataFrame(rows)


class FakeProvider(DataProvider):
    def __init__(self, code: str = "600519"):
        self.requested_codes = []
        self._info = StockInfo(
            code=code, symbol=code, name="测试股票", market=Market.A_SHARE
        )

    def get_klines(self, code: str) -> KlineResult:
        self.requested_codes.append(code)
        return KlineResult(info=self._info, klines=_make_klines(30))

    def get_fundamentals(self, code: str) -> FundamentalsResult:
        return FundamentalsResult(
            info=self._info,
            fundamentals=Fundamentals(pe_ttm=12.0, pb=2.0),
        )

    def search_symbols(self, query: str, limit: int = 10):
        if query == "测试股票":
            return [
                StockSearchResult(
                    code="600519",
                    symbol="600519",
                    name="测试股票",
                    market=Market.A_SHARE,
                    score=100,
                )
            ]
        if query.upper() == "APPLE":
            return [
                StockSearchResult(
                    code="AAPL",
                    symbol="AAPL",
                    name="苹果 Apple",
                    market=Market.US,
                    score=125,
                )
            ]
        return []


class TestRunAnalysis(unittest.TestCase):
    def setUp(self):
        self.provider = FakeProvider("600519")
        self.bundle = run_analysis("600519", provider=self.provider)

    def test_returns_analysis_bundle(self):
        self.assertIsInstance(self.bundle, AnalysisBundle)

    def test_composite_score_in_range(self):
        score = self.bundle.composite_result.score
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_value_result_not_none(self):
        self.assertIsNotNone(self.bundle.value_result)

    def test_bollinger_result_not_none(self):
        self.assertIsNotNone(self.bundle.bollinger_result)

    def test_fibonacci_result_not_none(self):
        self.assertIsNotNone(self.bundle.fibonacci_result)

    def test_price_action_result_not_none(self):
        self.assertIsNotNone(self.bundle.price_action_result)

    def test_info_code_matches(self):
        self.assertEqual(self.bundle.info.code, "600519")

    def test_fundamentals_propagated(self):
        self.assertEqual(self.bundle.fundamentals.pe_ttm, 12.0)
        self.assertEqual(self.bundle.fundamentals.pb, 2.0)

    def test_breakdown_keys_present(self):
        breakdown = self.bundle.composite_result.breakdown
        self.assertEqual(
            set(breakdown.keys()), {"value", "bollinger", "fibonacci", "price_action", "options"}
        )

    def test_data_quality_present(self):
        quality = self.bundle.data_quality

        self.assertGreaterEqual(quality.completeness, 0)
        self.assertLessEqual(quality.completeness, 1)
        self.assertEqual(quality.kline_days, 30)
        self.assertIn("ROE", quality.missing_fundamentals)
        self.assertTrue(quality.warnings)

    def test_resolves_name_query_before_analysis(self):
        provider = FakeProvider("600519")
        run_analysis("测试股票", provider=provider)

        self.assertEqual(provider.requested_codes[0], "600519")

    def test_resolves_company_name_that_looks_like_us_symbol_before_analysis(self):
        provider = FakeProvider("AAPL")
        run_analysis("APPLE", provider=provider)

        self.assertEqual(provider.requested_codes[0], "AAPL")

    def test_long_english_name_without_match_is_not_treated_as_ticker(self):
        provider = FakeProvider("ORACLE")

        with self.assertRaisesRegex(ValueError, "未找到匹配股票"):
            run_analysis("ORACLE", provider=provider)

        self.assertEqual(provider.requested_codes, [])

    def test_watchlist_summary_resolves_fuzzy_query_before_analysis(self):
        provider = FakeProvider("AAPL")
        rows = analyze_watchlist_items(
            [
                PortfolioItem(
                    code="APPLE",
                    symbol="APPLE",
                    name="Apple",
                    market=Market.US,
                )
            ],
            provider=provider,
        )

        self.assertEqual(provider.requested_codes[0], "AAPL")
        self.assertEqual(rows[0].code, "AAPL")

    def test_holding_summary_includes_profit_loss(self):
        provider = FakeProvider("600519")
        rows = analyze_watchlist_items(
            [
                HoldingItem(
                    code="600519",
                    symbol="600519",
                    name="测试股票",
                    market=Market.A_SHARE,
                    quantity=10,
                    cost_price=90,
                )
            ],
            provider=provider,
        )

        self.assertIsNotNone(rows[0].market_value)
        self.assertIsNotNone(rows[0].profit_loss)


class TestInsufficientKlines(unittest.TestCase):
    def test_pipeline_propagates_analyzer_error(self):
        class ShortKlineProvider(DataProvider):
            def __init__(self):
                self._info = StockInfo(
                    code="600519",
                    symbol="600519",
                    name="测试",
                    market=Market.A_SHARE,
                )

            def get_klines(self, code: str) -> KlineResult:
                return KlineResult(info=self._info, klines=_make_klines(10))

            def get_fundamentals(self, code: str) -> FundamentalsResult:
                return FundamentalsResult(
                    info=self._info, fundamentals=Fundamentals()
                )

        with self.assertRaises(ValueError):
            run_analysis("600519", provider=ShortKlineProvider())


if __name__ == "__main__":
    unittest.main()
