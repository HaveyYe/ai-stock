from dataclasses import dataclass, field
from typing import Dict

from src import config
from src.analyzers.value_analyzer import ValueResult
from src.analyzers.bollinger_analyzer import BollingerResult
from src.analyzers.fibonacci_analyzer import FibonacciResult


@dataclass
class CompositeResult:
    score: float
    action: str
    action_en: str
    breakdown: Dict[str, float] = field(default_factory=dict)
    weights: Dict[str, float] = field(default_factory=dict)


def compose(
    value_result: ValueResult,
    bollinger_result: BollingerResult,
    fibonacci_result: FibonacciResult,
) -> CompositeResult:
    weights = dict(config.SCORE_WEIGHTS)
    w_value = float(weights.get("value", 0.0))
    w_bollinger = float(weights.get("bollinger", 0.0))
    w_fibonacci = float(weights.get("fibonacci", 0.0))

    v_score = float(value_result.score)
    b_score = float(bollinger_result.score)
    f_score = float(fibonacci_result.score)

    raw = v_score * w_value + b_score * w_bollinger + f_score * w_fibonacci
    score = max(0.0, min(100.0, raw))
    score = round(score)

    if score >= 75:
        action = "买入"
        action_en = "Buy"
    elif score >= 60:
        action = "持有 / 逢低加仓"
        action_en = "Hold/Accumulate"
    elif score >= 40:
        action = "观望"
        action_en = "Wait"
    else:
        action = "谨慎 / 回避"
        action_en = "Caution"

    breakdown = {
        "value": v_score,
        "bollinger": b_score,
        "fibonacci": f_score,
    }

    return CompositeResult(
        score=score,
        action=action,
        action_en=action_en,
        breakdown=breakdown,
        weights=weights,
    )
