import unittest

import pandas as pd

from src.analyzers.options_analyzer import analyze, unavailable


class TestOptionsAnalyzer(unittest.TestCase):
    def test_analyzes_put_call_ratios_and_key_strikes(self):
        calls = pd.DataFrame(
            [
                {"strike": 105, "volume": 100, "openInterest": 300, "impliedVolatility": 0.3},
                {"strike": 110, "volume": 500, "openInterest": 900, "impliedVolatility": 0.35},
            ]
        )
        puts = pd.DataFrame(
            [
                {"strike": 95, "volume": 50, "openInterest": 700, "impliedVolatility": 0.4},
                {"strike": 90, "volume": 20, "openInterest": 100, "impliedVolatility": 0.45},
            ]
        )

        result = analyze(calls, puts, current_price=100, expiry="2026-07-17")

        self.assertTrue(result.available)
        self.assertEqual(result.expiry, "2026-07-17")
        self.assertAlmostEqual(result.put_call_volume_ratio, 70 / 600)
        self.assertEqual(result.support_strike, 95)
        self.assertEqual(result.resistance_strike, 110)
        self.assertGreater(result.score, 50)
        self.assertIn("期权", result.interpretation)

    def test_unavailable_result_does_not_participate_in_scoring(self):
        result = unavailable("not supported")

        self.assertFalse(result.available)
        self.assertEqual(result.confidence, 0)
        self.assertIn("not supported", result.warnings)


if __name__ == "__main__":
    unittest.main()
