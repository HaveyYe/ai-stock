import math
import unittest

from src.analyzers.value_analyzer import analyze
from src.types import Fundamentals


class TestValueAnalyzer(unittest.TestCase):
    def test_undervalued(self):
        result = analyze(Fundamentals(pe_ttm=10, pb=1.2, roe=20, dividend_yield=4))
        self.assertGreaterEqual(result.score, 75)
        self.assertEqual(result.label, "估值偏低")

    def test_overvalued(self):
        result = analyze(Fundamentals(pe_ttm=80, pb=10, roe=8))
        self.assertLess(result.score, 40)
        self.assertEqual(result.label, "估值偏高")

    def test_all_none(self):
        result = analyze(Fundamentals())
        self.assertEqual(result.score, 50)
        self.assertEqual(result.label, "基本面数据不可用")
        self.assertEqual(
            result.signals, ["基本面数据不可用，无法进行价值评估"]
        )
        for v in result.details.values():
            self.assertIsNone(v)

    def test_partial_none_only_pe(self):
        result = analyze(Fundamentals(pe_ttm=12))
        self.assertEqual(result.score, 90)
        self.assertEqual(len(result.signals), 1)

    def test_signals_non_empty(self):
        result = analyze(Fundamentals(pe_ttm=10, pb=1.2, roe=20, dividend_yield=4))
        self.assertGreaterEqual(len(result.signals), 1)

    def test_reasonable_range(self):
        result = analyze(Fundamentals(pe_ttm=20, pb=2.5))
        self.assertGreaterEqual(result.score, 40)
        self.assertLess(result.score, 75)
        self.assertEqual(result.label, "估值合理")

    def test_nan_treated_as_none(self):
        result = analyze(Fundamentals(pe_ttm=float("nan"), pb=math.nan))
        self.assertEqual(result.score, 50)
        self.assertEqual(result.label, "基本面数据不可用")

    def test_details_snapshot(self):
        result = analyze(Fundamentals(pe_ttm=10, roe=20))
        self.assertEqual(result.details["pe_ttm"], 10)
        self.assertEqual(result.details["roe"], 20)
        self.assertIsNone(result.details["pb"])
        self.assertIsNone(result.details["profit_growth"])


if __name__ == "__main__":
    unittest.main()
