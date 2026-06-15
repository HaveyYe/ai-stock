import math
from dataclasses import dataclass, field
from typing import List, Optional

from src.types import Fundamentals


@dataclass
class ValueResult:
    score: float
    label: str
    signals: List[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)


def _normalize_value(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f):
        return None
    return f


def _fmt(v: float) -> str:
    r = round(v, 2)
    if r == int(r):
        return str(int(r))
    return str(r)


def _score_pe(pe: float):
    if pe <= 0:
        return 50, f"市盈率 {_fmt(pe)}，亏损或异常，估值中性"
    if pe <= 15:
        return 90, f"市盈率 {_fmt(pe)}，处于低估区间"
    if pe <= 25:
        return 70, f"市盈率 {_fmt(pe)}，估值合理"
    if pe <= 40:
        return 50, f"市盈率 {_fmt(pe)}，估值偏高"
    if pe <= 60:
        return 30, f"市盈率 {_fmt(pe)}，估值明显偏高"
    return 15, f"市盈率 {_fmt(pe)}，估值明显偏高"


def _score_pb(pb: float):
    if pb <= 0:
        return 50, f"市净率 {_fmt(pb)}，异常，估值中性"
    if pb <= 1.5:
        return 85, f"市净率 {_fmt(pb)}，处于低估区间"
    if pb <= 3:
        return 65, f"市净率 {_fmt(pb)}，估值合理"
    if pb <= 5:
        return 45, f"市净率 {_fmt(pb)}，估值偏高"
    if pb <= 8:
        return 30, f"市净率 {_fmt(pb)}，估值明显偏高"
    return 15, f"市净率 {_fmt(pb)}，估值明显偏高"


def _score_roe(roe: float):
    if roe < 0:
        return 30, f"ROE {_fmt(roe)}%，盈利能力为负"
    if roe < 8:
        return 45, f"ROE {_fmt(roe)}%，盈利能力偏弱"
    if roe < 15:
        return 65, f"ROE {_fmt(roe)}%，盈利能力稳健"
    if roe < 20:
        return 85, f"ROE {_fmt(roe)}%，盈利能力较强"
    return 95, f"ROE {_fmt(roe)}%，盈利能力优秀"


def _score_dividend(dy: float):
    if dy < 1:
        return 40, f"股息率 {_fmt(dy)}%，分红偏低"
    if dy < 3:
        return 60, f"股息率 {_fmt(dy)}%，分红尚可"
    if dy < 5:
        return 80, f"股息率 {_fmt(dy)}%，分红较高"
    return 90, f"股息率 {_fmt(dy)}%，分红丰厚"


def _score_growth(g: float, name: str):
    if g < 0:
        return 35, f"{name} {_fmt(g)}%，出现下滑"
    if g < 10:
        return 55, f"{name} {_fmt(g)}%，增长平稳"
    if g < 25:
        return 75, f"{name} {_fmt(g)}%，增长较快"
    return 90, f"{name} {_fmt(g)}%，高速增长"


def analyze(fundamentals: Fundamentals) -> ValueResult:
    normalized = {
        "pe_ttm": _normalize_value(fundamentals.pe_ttm),
        "pb": _normalize_value(fundamentals.pb),
        "roe": _normalize_value(fundamentals.roe),
        "dividend_yield": _normalize_value(fundamentals.dividend_yield),
        "revenue_growth": _normalize_value(fundamentals.revenue_growth),
        "profit_growth": _normalize_value(fundamentals.profit_growth),
    }

    if all(v is None for v in normalized.values()):
        return ValueResult(
            score=50,
            label="基本面数据不可用",
            signals=["基本面数据不可用，无法进行价值评估"],
            details=normalized,
        )

    scores: List[float] = []
    signals: List[str] = []

    if normalized["pe_ttm"] is not None:
        s, sig = _score_pe(normalized["pe_ttm"])
        scores.append(s)
        signals.append(sig)

    if normalized["pb"] is not None:
        s, sig = _score_pb(normalized["pb"])
        scores.append(s)
        signals.append(sig)

    if normalized["roe"] is not None:
        s, sig = _score_roe(normalized["roe"])
        scores.append(s)
        signals.append(sig)

    if normalized["dividend_yield"] is not None:
        s, sig = _score_dividend(normalized["dividend_yield"])
        scores.append(s)
        signals.append(sig)

    if normalized["revenue_growth"] is not None:
        s, sig = _score_growth(normalized["revenue_growth"], "营收增长")
        scores.append(s)
        signals.append(sig)

    if normalized["profit_growth"] is not None:
        s, sig = _score_growth(normalized["profit_growth"], "利润增长")
        scores.append(s)
        signals.append(sig)

    score = round(sum(scores) / len(scores))

    if score >= 75:
        label = "估值偏低"
    elif score >= 40:
        label = "估值合理"
    else:
        label = "估值偏高"

    return ValueResult(score=score, label=label, signals=signals, details=normalized)
