import unittest

from src.scoring.composer import CompositeResult, compose
from src.analyzers.value_analyzer import ValueResult
from src.analyzers.bollinger_analyzer import BollingerResult
from src.analyzers.fibonacci_analyzer import FibonacciResult
from src.analyzers.price_action_analyzer import PriceActionResult
from src.types import OptionAnalysisResult


def _p(score=80, **kwargs):
    return PriceActionResult(score=score, label=kwargs.pop("label", "价格行为偏强"), **kwargs)


class TestComposer(unittest.TestCase):
    def test_high_score_buy(self):
        v = ValueResult(score=85, label="估值偏低", signals=[], details={})
        b = BollingerResult(score=80)
        f = FibonacciResult(score=82)
        result = compose(v, b, f, _p(84))

        self.assertIsInstance(result, CompositeResult)
        self.assertEqual(result.score, 83)
        self.assertEqual(result.action, "机会关注")
        self.assertEqual(result.action_en, "Opportunity")
        self.assertEqual(result.risk_level, "低")

    def test_low_score_caution(self):
        v = ValueResult(score=25, label="估值偏高", signals=[], details={})
        b = BollingerResult(score=20)
        f = FibonacciResult(score=22)
        result = compose(v, b, f, _p(20))

        self.assertEqual(result.score, 22)
        self.assertEqual(result.action, "风险回避")
        self.assertEqual(result.action_en, "Avoid")

    def test_mid_score_accumulate(self):
        v = ValueResult(score=65, label="估值合理", signals=[], details={})
        b = BollingerResult(score=60)
        f = FibonacciResult(score=62)
        result = compose(v, b, f, _p(64))

        self.assertEqual(result.score, 63)
        self.assertEqual(result.action, "谨慎观察")
        self.assertEqual(result.action_en, "Watch")

    def test_mid_score_wait(self):
        v = ValueResult(score=50, label="估值合理", signals=[], details={})
        b = BollingerResult(score=45)
        f = FibonacciResult(score=42)
        result = compose(v, b, f, _p(45))

        self.assertEqual(result.score, 46)
        self.assertEqual(result.action, "中性观察")
        self.assertEqual(result.action_en, "Neutral")

    def test_breakdown_keys_and_values(self):
        v = ValueResult(score=85, label="估值偏低", signals=[], details={})
        b = BollingerResult(score=80)
        f = FibonacciResult(score=82)
        result = compose(v, b, f, _p(84))

        self.assertEqual(set(result.breakdown.keys()), {"value", "bollinger", "fibonacci", "price_action", "options"})
        self.assertEqual(result.breakdown["value"], 85)
        self.assertEqual(result.breakdown["bollinger"], 80)
        self.assertEqual(result.breakdown["fibonacci"], 82)
        self.assertEqual(result.breakdown["price_action"], 84)
        self.assertEqual(result.breakdown["options"], 0)

    def test_weights_equal_config(self):
        v = ValueResult(score=85, label="估值偏低", signals=[], details={})
        b = BollingerResult(score=80)
        f = FibonacciResult(score=82)
        result = compose(v, b, f, _p(84))

        self.assertEqual(
            result.weights,
            {
                "value": 0.3111111111111111,
                "bollinger": 0.2333333333333333,
                "fibonacci": 0.19999999999999998,
                "price_action": 0.25555555555555554,
                "options": 0.0,
            },
        )

    def test_available_options_participate_with_low_weight(self):
        v = ValueResult(score=60, label="估值合理", signals=[], details={})
        b = BollingerResult(score=60)
        f = FibonacciResult(score=60)
        option = OptionAnalysisResult(available=True, score=90, label="期权情绪偏积极", confidence=0.8)
        result = compose(v, b, f, _p(60), option)

        self.assertGreater(result.score, 60)
        self.assertGreater(result.weights["options"], 0)

    def test_score_clamped_within_range(self):
        v = ValueResult(score=200, label="异常", signals=[], details={})
        b = BollingerResult(score=200)
        f = FibonacciResult(score=200)
        result = compose(v, b, f, _p(200))

        self.assertLessEqual(result.score, 100)
        self.assertGreaterEqual(result.score, 0)

    def test_conflict_lowers_confidence(self):
        v = ValueResult(score=85, label="估值偏低", signals=[], details={})
        b = BollingerResult(score=30, label="超买")
        f = FibonacciResult(score=35)
        result = compose(v, b, f, _p(30))

        self.assertTrue(result.conflicts)
        self.assertLess(result.confidence, 1.0)
        self.assertIn(result.risk_level, {"中", "高"})

    def test_low_confidence_does_not_emit_opportunity(self):
        v = ValueResult(score=95, label="估值偏低", signals=[], details={}, confidence=0.2)
        b = BollingerResult(score=90, confidence=0.3)
        f = FibonacciResult(score=90, confidence=0.3)
        result = compose(v, b, f, _p(90, confidence=0.3))

        self.assertNotEqual(result.action, "机会关注")
        self.assertLess(result.confidence, 0.65)

    def test_zero_weights_are_normalized(self):
        old = dict(__import__("src.config", fromlist=["SCORE_WEIGHTS"]).SCORE_WEIGHTS)
        try:
            config = __import__("src.config", fromlist=["SCORE_WEIGHTS"])
            config.SCORE_WEIGHTS = {"value": 0, "bollinger": 0, "fibonacci": 0, "price_action": 0}
            result = compose(
                ValueResult(score=90, label="", signals=[], details={}),
                BollingerResult(score=60),
                FibonacciResult(score=30),
                _p(20),
            )
            self.assertEqual(result.weights, {"value": 0.25, "bollinger": 0.25, "fibonacci": 0.25, "price_action": 0.25, "options": 0.0})
            self.assertEqual(result.score, 50)
        finally:
            __import__("src.config", fromlist=["SCORE_WEIGHTS"]).SCORE_WEIGHTS = old


if __name__ == "__main__":
    unittest.main()
