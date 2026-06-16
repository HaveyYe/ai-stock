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
