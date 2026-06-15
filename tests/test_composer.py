import unittest

from src.scoring.composer import CompositeResult, compose
from src.analyzers.value_analyzer import ValueResult
from src.analyzers.bollinger_analyzer import BollingerResult
from src.analyzers.fibonacci_analyzer import FibonacciResult


class TestComposer(unittest.TestCase):
    def test_high_score_buy(self):
        v = ValueResult(score=85, label="估值偏低", signals=[], details={})
        b = BollingerResult(score=80)
        f = FibonacciResult(score=82)
        result = compose(v, b, f)

        self.assertIsInstance(result, CompositeResult)
        self.assertEqual(result.score, 83)
        self.assertEqual(result.action, "买入")
        self.assertEqual(result.action_en, "Buy")

    def test_low_score_caution(self):
        v = ValueResult(score=25, label="估值偏高", signals=[], details={})
        b = BollingerResult(score=20)
        f = FibonacciResult(score=22)
        result = compose(v, b, f)

        self.assertEqual(result.score, 23)
        self.assertEqual(result.action, "谨慎 / 回避")
        self.assertEqual(result.action_en, "Caution")

    def test_mid_score_accumulate(self):
        v = ValueResult(score=65, label="估值合理", signals=[], details={})
        b = BollingerResult(score=60)
        f = FibonacciResult(score=62)
        result = compose(v, b, f)

        self.assertEqual(result.score, 63)
        self.assertEqual(result.action, "持有 / 逢低加仓")
        self.assertEqual(result.action_en, "Hold/Accumulate")

    def test_mid_score_wait(self):
        v = ValueResult(score=50, label="估值合理", signals=[], details={})
        b = BollingerResult(score=45)
        f = FibonacciResult(score=42)
        result = compose(v, b, f)

        self.assertEqual(result.score, 46)
        self.assertEqual(result.action, "观望")
        self.assertEqual(result.action_en, "Wait")

    def test_breakdown_keys_and_values(self):
        v = ValueResult(score=85, label="估值偏低", signals=[], details={})
        b = BollingerResult(score=80)
        f = FibonacciResult(score=82)
        result = compose(v, b, f)

        self.assertEqual(set(result.breakdown.keys()), {"value", "bollinger", "fibonacci"})
        self.assertEqual(result.breakdown["value"], 85)
        self.assertEqual(result.breakdown["bollinger"], 80)
        self.assertEqual(result.breakdown["fibonacci"], 82)

    def test_weights_equal_config(self):
        v = ValueResult(score=85, label="估值偏低", signals=[], details={})
        b = BollingerResult(score=80)
        f = FibonacciResult(score=82)
        result = compose(v, b, f)

        self.assertEqual(
            result.weights,
            {"value": 0.4, "bollinger": 0.3, "fibonacci": 0.3},
        )

    def test_score_clamped_within_range(self):
        v = ValueResult(score=200, label="异常", signals=[], details={})
        b = BollingerResult(score=200)
        f = FibonacciResult(score=200)
        result = compose(v, b, f)

        self.assertLessEqual(result.score, 100)
        self.assertGreaterEqual(result.score, 0)


if __name__ == "__main__":
    unittest.main()
