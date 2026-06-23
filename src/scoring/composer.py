from dataclasses import dataclass, field
from typing import Dict, List

from src import config
from src.analyzers.value_analyzer import ValueResult
from src.analyzers.bollinger_analyzer import BollingerResult
from src.analyzers.fibonacci_analyzer import FibonacciResult
from src.analyzers.price_action_analyzer import PriceActionResult
from src.types import OptionAnalysisResult


@dataclass
class CompositeResult:
    score: float
    action: str
    action_en: str
    breakdown: Dict[str, float] = field(default_factory=dict)
    weights: Dict[str, float] = field(default_factory=dict)
    confidence: float = 1.0
    risk_level: str = "中"
    summary: str = ""
    conflicts: List[str] = field(default_factory=list)
    signal_conflicts: List[str] = field(default_factory=list)


def _normalized_weights(weights: Dict[str, float], include_options: bool = False) -> Dict[str, float]:
    keys = ["value", "bollinger", "fibonacci", "price_action"]
    if include_options:
        keys.append("options")
    cleaned = {k: max(0.0, float(weights.get(k, 0.0))) for k in keys}
    total = sum(cleaned.values())
    if total <= 0:
        return {k: 1 / len(keys) for k in keys}
    return {k: v / total for k, v in cleaned.items()}


def _confidence(result) -> float:
    try:
        value = float(getattr(result, "confidence", 1.0))
    except (TypeError, ValueError):
        value = 1.0
    return max(0.0, min(1.0, value))


def _find_conflicts(
    value_result: ValueResult,
    bollinger_result: BollingerResult,
    fibonacci_result: FibonacciResult,
    price_action_result: PriceActionResult,
    option_result: OptionAnalysisResult | None = None,
) -> List[str]:
    conflicts: List[str] = []
    v_score = float(value_result.score)
    b_score = float(bollinger_result.score)
    f_score = float(fibonacci_result.score)
    p_score = float(price_action_result.score)

    if v_score >= 70 and (b_score <= 40 or f_score <= 40 or p_score <= 40):
        conflicts.append("基本面较好，但至少一个技术指标提示短线风险")
    if v_score <= 40 and (b_score >= 60 or f_score >= 60 or p_score >= 60):
        conflicts.append("技术位置出现机会，但基本面评分偏弱")
    if "超买" in getattr(bollinger_result, "label", "") and f_score <= 45:
        conflicts.append("布林带偏超买且斐波那契接近压力区，追高风险较高")
    if p_score >= 70 and b_score <= 40:
        conflicts.append("价格行为偏强，但布林带提示短线过热")
    if p_score <= 35 and (b_score >= 60 or f_score >= 55):
        conflicts.append("位置指标出现机会，但价格行为仍处弱势结构")
    if getattr(price_action_result, "breakout_state", "") == "向上突破" and getattr(price_action_result, "volume_ratio", None) is not None:
        if float(price_action_result.volume_ratio) < 1.1:
            conflicts.append("价格突破缺少成交量确认，假突破风险较高")
    if _confidence(value_result) < 0.5:
        conflicts.append("基本面数据不足，估值结论可信度偏低")
    if min(
        _confidence(value_result),
        _confidence(bollinger_result),
        _confidence(fibonacci_result),
        _confidence(price_action_result),
    ) < 0.5:
        conflicts.append("至少一个分析维度数据置信度偏低")
    if option_result is not None and option_result.available:
        option_score = float(option_result.score)
        if option_score <= 40 and p_score >= 60:
            conflicts.append("正股技术面偏强，但期权市场避险或波动信号偏高")
        if option_score >= 65 and (b_score <= 40 or p_score <= 40):
            conflicts.append("期权情绪偏积极，但正股技术结构尚未确认")

    return conflicts


def compose(
    value_result: ValueResult,
    bollinger_result: BollingerResult,
    fibonacci_result: FibonacciResult,
    price_action_result: PriceActionResult,
    option_result: OptionAnalysisResult | None = None,
) -> CompositeResult:
    include_options = bool(option_result is not None and option_result.available)
    weights = _normalized_weights(dict(config.SCORE_WEIGHTS), include_options=include_options)
    w_value = float(weights.get("value", 0.0))
    w_bollinger = float(weights.get("bollinger", 0.0))
    w_fibonacci = float(weights.get("fibonacci", 0.0))
    w_price_action = float(weights.get("price_action", 0.0))
    w_options = float(weights.get("options", 0.0))

    v_score = float(value_result.score)
    b_score = float(bollinger_result.score)
    f_score = float(fibonacci_result.score)
    p_score = float(price_action_result.score)
    o_score = float(option_result.score) if option_result is not None and option_result.available else 0.0

    raw = (
        v_score * w_value
        + b_score * w_bollinger
        + f_score * w_fibonacci
        + p_score * w_price_action
        + o_score * w_options
    )
    score = max(0.0, min(100.0, raw))
    score = round(score)

    conflicts = _find_conflicts(value_result, bollinger_result, fibonacci_result, price_action_result, option_result)
    confidence = (
        _confidence(value_result) * w_value
        + _confidence(bollinger_result) * w_bollinger
        + _confidence(fibonacci_result) * w_fibonacci
        + _confidence(price_action_result) * w_price_action
        + (_confidence(option_result) * w_options if include_options else 0.0)
    )
    if conflicts:
        confidence *= max(0.65, 1 - 0.1 * len(conflicts))
    confidence = round(max(0.0, min(1.0, confidence)), 2)

    if score >= 75 and confidence >= 0.65 and len(conflicts) <= 1:
        action = "机会关注"
        action_en = "Opportunity"
    elif score >= 60:
        action = "谨慎观察"
        action_en = "Watch"
    elif score >= 40:
        action = "中性观察"
        action_en = "Neutral"
    else:
        action = "风险回避"
        action_en = "Avoid"

    if score < 40 or len(conflicts) >= 2 or confidence < 0.45:
        risk_level = "高"
    elif score < 60 or conflicts or confidence < 0.65:
        risk_level = "中"
    else:
        risk_level = "低"

    if action == "机会关注":
        summary = "多维评分偏积极，但仍需结合仓位和止损纪律。"
    elif action == "谨慎观察":
        summary = "存在部分机会信号，但确认度不足，适合等待更清晰的量价配合。"
    elif action == "中性观察":
        summary = "多维信号没有形成明确共振，保持观察更稳妥。"
    else:
        summary = "风险信号占优或数据可信度不足，暂不适合激进参与。"

    breakdown = {
        "value": v_score,
        "bollinger": b_score,
        "fibonacci": f_score,
        "price_action": p_score,
        "options": o_score,
    }
    if not include_options:
        weights["options"] = 0.0

    return CompositeResult(
        score=score,
        action=action,
        action_en=action_en,
        breakdown=breakdown,
        weights=weights,
        confidence=confidence,
        risk_level=risk_level,
        summary=summary,
        conflicts=conflicts,
        signal_conflicts=conflicts,
    )
