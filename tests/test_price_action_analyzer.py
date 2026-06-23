import unittest
from datetime import datetime, timedelta

import pandas as pd

from src.analyzers.price_action_analyzer import PriceActionResult, analyze


def _klines_from_closes(closes, volumes=None):
    rows = []
    volumes = volumes or [1000] * len(closes)
    for i, close in enumerate(closes):
        open_price = closes[i - 1] if i else close
        high = max(open_price, close) + 1
        low = min(open_price, close) - 1
        rows.append(
            {
                "date": datetime(2024, 1, 1) + timedelta(days=i),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volumes[i],
            }
        )
    return pd.DataFrame(rows)


class TestPriceActionAnalyzer(unittest.TestCase):
    def test_detects_uptrend_breakout_with_volume(self):
        closes = [100 + i * 0.5 for i in range(59)] + [134]
        volumes = [1000] * 59 + [1800]

        result = analyze(_klines_from_closes(closes, volumes), window=60)

        self.assertIsInstance(result, PriceActionResult)
        self.assertEqual(result.breakout_state, "向上突破")
        self.assertGreaterEqual(result.score, 75)
        self.assertTrue(any("突破" in signal for signal in result.signals))
        self.assertGreater(result.volume_ratio, 1.3)

    def test_penalizes_breakout_without_volume(self):
        closes = [100 + i * 0.35 for i in range(59)] + [125]
        volumes = [1000] * 60

        result = analyze(_klines_from_closes(closes, volumes), window=60)

        self.assertEqual(result.breakout_state, "向上突破")
        self.assertTrue(any("量能不足" in risk for risk in result.risks))

    def test_detects_breakdown_risk(self):
        closes = [140 - i * 0.45 for i in range(59)] + [100]
        volumes = [1000] * 59 + [1500]

        result = analyze(_klines_from_closes(closes, volumes), window=60)

        self.assertEqual(result.breakout_state, "向下跌破")
        self.assertLessEqual(result.score, 30)
        self.assertTrue(any("跌破" in risk for risk in result.risks))

    def test_support_does_not_remain_above_current_after_breakdown(self):
        rows = []
        lows = [
            9.88, 9.14, 9.23, 9.50, 9.44, 9.81, 9.86, 9.88, 10.04, 10.25,
            10.27, 10.55, 10.59, 10.50, 9.29, 9.43, 9.07, 9.09, 9.06, 9.33,
            9.45, 9.60, 8.69, 8.38, 8.29,
        ]
        closes = [
            10.02, 9.34, 9.66, 9.77, 9.80, 10.18, 10.00, 10.16, 10.41, 10.34,
            10.68, 10.79, 10.74, 10.54, 9.47, 9.69, 9.33, 9.14, 9.58, 9.34,
            9.53, 9.62, 8.73, 8.46, 8.34,
        ]
        highs = [
            10.20, 9.89, 9.80, 9.84, 9.97, 10.36, 10.44, 10.17, 10.53, 10.57,
            10.83, 11.25, 11.10, 10.92, 10.46, 9.86, 10.02, 9.33, 9.60, 9.60,
            9.89, 10.26, 9.63, 8.80, 8.56,
        ]
        for i, close in enumerate(closes):
            rows.append(
                {
                    "date": datetime(2024, 1, 1) + timedelta(days=i),
                    "open": closes[i - 1] if i else close,
                    "high": highs[i],
                    "low": lows[i],
                    "close": close,
                    "volume": 1000,
                }
            )

        result = analyze(pd.DataFrame(rows), window=25)

        self.assertLessEqual(result.support, result.current_price)
        self.assertGreaterEqual(result.resistance, result.current_price)
        self.assertTrue(any("前支撑" in risk for risk in result.risks))

    def test_ignores_latest_intraday_low_as_primary_support(self):
        rows = []
        closes = [100, 102, 104, 106, 108, 110, 109, 108, 107, 106, 105, 104, 106, 108, 110, 112, 114, 116, 118, 120, 119, 118, 117, 116, 120]
        for i, close in enumerate(closes):
            rows.append(
                {
                    "date": datetime(2024, 1, 1) + timedelta(days=i),
                    "open": close - 0.5,
                    "high": close + 1.0,
                    "low": close - 1.0,
                    "close": close,
                    "volume": 1000,
                }
            )
        rows[-1]["low"] = 119.8

        result = analyze(pd.DataFrame(rows), window=25)

        self.assertLess(result.support, 119)

    def test_missing_volume_lowers_confidence(self):
        df = _klines_from_closes([100 + i for i in range(30)]).drop(columns=["volume"])

        result = analyze(df, window=30)

        self.assertLess(result.confidence, 0.88)
        self.assertTrue(any("成交量" in warning for warning in result.data_warnings))

    def test_requires_enough_rows(self):
        with self.assertRaises(ValueError):
            analyze(_klines_from_closes([100 + i for i in range(10)]))


if __name__ == "__main__":
    unittest.main()
