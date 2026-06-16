import unittest

import pandas as pd

from src.analyzers.bollinger_analyzer import analyze, BollingerResult


def make_df(closes):
    return pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2024-01-01") + pd.Timedelta(days=i),
                "open": c,
                "close": c,
                "high": c + 1,
                "low": c - 1,
                "volume": 1000,
            }
            for i, c in enumerate(closes)
        ]
    )


class TestBollingerAnalyzer(unittest.TestCase):
    def test_oversold_when_close_far_below_lower(self):
        closes = [100.0] * 24 + [50.0]
        result = analyze(make_df(closes))
        self.assertIsInstance(result, BollingerResult)
        self.assertGreaterEqual(result.score, 55)
        self.assertTrue("超卖" in result.label or "接近下轨" in result.label)
        self.assertLess(result.percent_b, 0.2)
        self.assertTrue(len(result.signals) >= 1)
        self.assertIn("不等同于趋势反转", " ".join(result.signals))
        self.assertGreater(result.confidence, 0)

    def test_overbought_when_close_far_above_upper(self):
        closes = [100.0] * 24 + [150.0]
        result = analyze(make_df(closes))
        self.assertIsInstance(result, BollingerResult)
        self.assertLessEqual(result.score, 30)
        self.assertTrue("超买" in result.label or "接近上轨" in result.label)
        self.assertGreater(result.percent_b, 0.8)

    def test_neutral_when_close_near_middle(self):
        closes = [100.0] * 25
        result = analyze(make_df(closes))
        self.assertEqual(result.score, 50)
        self.assertEqual(result.label, "中性区间")
        self.assertGreaterEqual(result.percent_b, 0.2)
        self.assertLess(result.percent_b, 0.8)

    def test_insufficient_data_raises(self):
        closes = [100.0] * 15
        with self.assertRaises(ValueError):
            analyze(make_df(closes))

    def test_band_structure_lower_middle_upper(self):
        closes = []
        for i in range(25):
            closes.append(100.0 + (1.0 if i % 2 == 0 else -1.0))
        result = analyze(make_df(closes))
        self.assertLess(result.lower, result.middle)
        self.assertLess(result.middle, result.upper)

    def test_missing_close_column_raises(self):
        df = pd.DataFrame(
            [
                {
                    "date": pd.Timestamp("2024-01-01") + pd.Timedelta(days=i),
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "volume": 1000,
                }
                for i in range(25)
            ]
        )
        with self.assertRaises(ValueError):
            analyze(df)

    def test_custom_window_and_num_std(self):
        closes = [100.0] * 29 + [50.0]
        result = analyze(make_df(closes), window=30, num_std=2.0)
        self.assertIsInstance(result, BollingerResult)
        self.assertGreaterEqual(result.score, 55)

    def test_bandwidth_percentile_in_range(self):
        closes = [100.0] * 24 + [50.0]
        result = analyze(make_df(closes))
        self.assertGreaterEqual(result.bandwidth_percentile, 0.0)
        self.assertLessEqual(result.bandwidth_percentile, 1.0)

    def test_squeeze_signal_when_low_percentile(self):
        closes = [100.0] + [100.0 + (0.01 * (i % 3 - 1)) for i in range(1, 120)]
        closes[-1] = closes[-2]
        result = analyze(make_df(closes))
        self.assertTrue(
            any("带宽收缩" in s for s in result.signals)
            or result.bandwidth_percentile > 0.2
        )


if __name__ == "__main__":
    unittest.main()
