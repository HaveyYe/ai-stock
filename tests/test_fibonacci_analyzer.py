import unittest

import pandas as pd

from src.analyzers.fibonacci_analyzer import analyze, FibonacciResult


def make_df(prices):
    rows = [
        {
            "date": pd.Timestamp("2024-01-01") + pd.Timedelta(days=i),
            "open": p,
            "close": p,
            "high": p + 5,
            "low": p - 5,
            "volume": 1000,
        }
        for i, p in enumerate(prices)
    ]
    return pd.DataFrame(rows)


class TestFibonacciAnalyzer(unittest.TestCase):
    def test_golden_zone_score_85(self):
        prices = [150] * 125 + [195, 105, 155]
        df = make_df(prices)
        result = analyze(df)
        self.assertEqual(result.score, 85)
        self.assertIn("黄金支撑", result.label)
        self.assertAlmostEqual(result.position_ratio, 0.55, places=2)
        self.assertEqual(result.swing_high, 200)
        self.assertEqual(result.swing_low, 100)

    def test_near_high_score_40(self):
        prices = [150] * 125 + [195, 105]
        df = make_df(prices)
        result = analyze(df)
        self.assertEqual(result.score, 40)
        self.assertAlmostEqual(result.position_ratio, 0.05, places=2)

    def test_breakout_score_25(self):
        prices = [150] * 125 + [195, 105, 150]
        df = make_df(prices)
        df.loc[df.index[-1], "close"] = 210
        result = analyze(df)
        self.assertEqual(result.score, 25)
        self.assertAlmostEqual(result.position_ratio, 1.1, places=2)

    def test_levels_keys_and_values(self):
        prices = [150] * 125 + [195, 105, 155]
        df = make_df(prices)
        result = analyze(df)
        self.assertEqual(len(result.levels), 7)
        self.assertEqual(result.levels[0.0], 100.0)
        self.assertEqual(result.levels[0.5], 150.0)
        self.assertEqual(result.levels[1.0], 200.0)

    def test_empty_df_raises_value_error(self):
        df = pd.DataFrame(columns=["date", "open", "close", "high", "low", "volume"])
        with self.assertRaises(ValueError):
            analyze(df)

    def test_returns_fibonacci_result_with_signals(self):
        prices = [150] * 125 + [195, 105, 155]
        df = make_df(prices)
        result = analyze(df)
        self.assertIsInstance(result, FibonacciResult)
        self.assertGreaterEqual(len(result.signals), 2)


if __name__ == "__main__":
    unittest.main()
