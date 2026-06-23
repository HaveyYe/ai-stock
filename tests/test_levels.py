import unittest

from src.analyzers.levels import combine_support_resistance
from src.analyzers.price_action_analyzer import PriceActionResult
from src.types import OptionAnalysisResult


class TestSupportResistanceLevels(unittest.TestCase):
    def test_uses_nearest_option_levels_when_more_actionable(self):
        result = combine_support_resistance(
            PriceActionResult(
                score=50,
                support=100,
                resistance=140,
                current_price=120,
            ),
            OptionAnalysisResult(
                available=True,
                support_strike=116,
                resistance_strike=126,
            ),
        )

        self.assertEqual(result.support, 116)
        self.assertEqual(result.resistance, 126)
        self.assertEqual(result.support_source, "Put密集区")
        self.assertEqual(result.resistance_source, "Call密集区")

    def test_merges_nearby_stock_and_option_levels_as_confluence(self):
        result = combine_support_resistance(
            PriceActionResult(
                score=50,
                support=112,
                resistance=128,
                current_price=124,
            ),
            OptionAnalysisResult(
                available=True,
                support_strike=115,
                resistance_strike=130,
            ),
        )

        self.assertAlmostEqual(result.support, 113.5)
        self.assertAlmostEqual(result.resistance, 129.0)
        self.assertEqual(result.support_source, "正股技术位+Put密集区共振")
        self.assertEqual(result.resistance_source, "正股技术位+Call密集区共振")

    def test_ignores_option_levels_on_wrong_side_of_current_price(self):
        result = combine_support_resistance(
            PriceActionResult(
                score=50,
                support=96,
                resistance=112,
                current_price=105,
            ),
            OptionAnalysisResult(
                available=True,
                support_strike=108,
                resistance_strike=101,
            ),
        )

        self.assertEqual(result.support, 96)
        self.assertEqual(result.resistance, 112)
        self.assertEqual(result.support_source, "正股技术位")
        self.assertEqual(result.resistance_source, "正股技术位")

    def test_ignores_too_close_stock_noise_when_options_are_significant(self):
        result = combine_support_resistance(
            PriceActionResult(
                score=50,
                support=296.76,
                resistance=297.14,
                current_price=297.01,
            ),
            OptionAnalysisResult(
                available=True,
                support_strike=290,
                resistance_strike=302.5,
            ),
        )

        self.assertEqual(result.support, 290)
        self.assertEqual(result.resistance, 302.5)
        self.assertEqual(result.support_source, "Put密集区")
        self.assertEqual(result.resistance_source, "Call密集区")


if __name__ == "__main__":
    unittest.main()
