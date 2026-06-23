from dataclasses import dataclass
from typing import Optional

import pandas as pd

from src.analyzers.price_action_analyzer import PriceActionResult
from src.types import OptionAnalysisResult, SupportResistanceResult


@dataclass
class _LevelCandidate:
    value: float
    source: str


def _to_float(value) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def _add_directional_candidate(
    candidates: list[_LevelCandidate],
    value,
    source: str,
    current_price: Optional[float],
    side: str,
    min_distance: float = 0.0,
) -> None:
    number = _to_float(value)
    if number is None:
        return
    if current_price is not None:
        if side == "support" and number > current_price:
            return
        if side == "resistance" and number < current_price:
            return
        if abs(current_price - number) < min_distance:
            return
    candidates.append(_LevelCandidate(number, source))


def _select_level(
    candidates: list[_LevelCandidate],
    current_price: Optional[float],
    side: str,
) -> tuple[Optional[float], str]:
    if not candidates:
        return None, "数据不可用"
    if current_price is None:
        best = candidates[0]
        return best.value, best.source

    ordered = sorted(candidates, key=lambda item: abs(current_price - item.value))
    best = ordered[0]
    band = max(abs(current_price) * 0.025, 0.01)
    cluster = [item for item in ordered if abs(item.value - best.value) <= band]
    if len(cluster) <= 1:
        return best.value, best.source

    value = sum(item.value for item in cluster) / len(cluster)
    source_order = {"正股技术位": 0, "Put密集区": 1, "Call密集区": 1}
    sources = []
    for item in sorted(cluster, key=lambda candidate: source_order.get(candidate.source, 99)):
        if item.source not in sources:
            sources.append(item.source)
    source = "+".join(sources) + "共振"
    return value, source


def combine_support_resistance(
    price_action_result: PriceActionResult,
    option_result: Optional[OptionAnalysisResult] = None,
    current_price: Optional[float] = None,
) -> SupportResistanceResult:
    current = _to_float(current_price)
    if current is None:
        current = _to_float(getattr(price_action_result, "current_price", None))
    min_distance = max(abs(current) * 0.01, 0.01) if current is not None else 0.0

    supports: list[_LevelCandidate] = []
    resistances: list[_LevelCandidate] = []
    _add_directional_candidate(
        supports,
        getattr(price_action_result, "support", None),
        "正股技术位",
        current,
        "support",
        min_distance,
    )
    _add_directional_candidate(
        resistances,
        getattr(price_action_result, "resistance", None),
        "正股技术位",
        current,
        "resistance",
        min_distance,
    )

    if option_result is not None and getattr(option_result, "available", False):
        _add_directional_candidate(
            supports,
            getattr(option_result, "support_strike", None),
            "Put密集区",
            current,
            "support",
            min_distance,
        )
        _add_directional_candidate(
            resistances,
            getattr(option_result, "resistance_strike", None),
            "Call密集区",
            current,
            "resistance",
            min_distance,
        )

    support, support_source = _select_level(supports, current, "support")
    resistance, resistance_source = _select_level(resistances, current, "resistance")

    signals = [
        f"综合支撑来自{support_source}",
        f"综合压力来自{resistance_source}",
    ]
    return SupportResistanceResult(
        support=support,
        resistance=resistance,
        support_source=support_source,
        resistance_source=resistance_source,
        signals=signals,
    )
