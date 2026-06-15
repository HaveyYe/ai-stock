import unittest
from datetime import datetime, timedelta

import pandas as pd

from src.data.provider import DataProvider
from src.pipeline import AnalysisBundle, run_analysis
from src.types import (
    Fundamentals,
    FundamentalsResult,
    KlineResult,
    Market,
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
        self._info = StockInfo(
            code=code, symbol=code, name="测试股票", market=Market.A_SHARE
        )

    def get_klines(self, code: str) -> KlineResult:
        return KlineResult(info=self._info, klines=_make_klines(30))

    def get_fundamentals(self, code: str) -> FundamentalsResult:
        return FundamentalsResult(
            info=self._info,
            fundamentals=Fundamentals(pe_ttm=12.0, pb=2.0),
        )


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

    def test_info_code_matches(self):
        self.assertEqual(self.bundle.info.code, "600519")

    def test_fundamentals_propagated(self):
        self.assertEqual(self.bundle.fundamentals.pe_ttm, 12.0)
        self.assertEqual(self.bundle.fundamentals.pb, 2.0)

    def test_breakdown_keys_present(self):
        breakdown = self.bundle.composite_result.breakdown
        self.assertEqual(
            set(breakdown.keys()), {"value", "bollinger", "fibonacci"}
        )


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
