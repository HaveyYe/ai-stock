import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from src.types import Fundamentals, Market


@dataclass
class ValueResult:
    score: float
    label: str
    signals: List[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)
    confidence: float = 1.0
    data_warnings: List[str] = field(default_factory=list)
    interpretation: str = ""


_METRIC_LABELS = {
    "pe_ttm": "PE(TTM)",
    "pb": "PB",
    "roe": "ROE",
    "dividend_yield": "股息率",
    "revenue_growth": "营收增长",
    "profit_growth": "利润增长",
}

_PE_RULES: Dict[Market, Tuple[float, float, float, float]] = {
    Market.A_SHARE: (15, 25, 40, 60),
    Market.HK: (10, 18, 30, 45),
    Market.US: (20, 35, 55, 80),
}

_PB_RULES: Dict[Market, Tuple[float, float, float, float]] = {
    Market.A_SHARE: (1.5, 3, 5, 8),
    Market.HK: (1.0, 2, 3.5, 6),
    Market.US: (3, 6, 10, 16),
}


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


def _market_name(market: Optional[Market]) -> str:
    if market is Market.HK:
        return "港股"
    if market is Market.US:
        return "美股"
    return "A股"


def _score_pe(pe: float, market: Optional[Market]):
    if pe <= 0:
        return 50, f"市盈率 {_fmt(pe)}，亏损或异常，估值中性"
    low, fair, high, extreme = _PE_RULES.get(market, _PE_RULES[Market.A_SHARE])
    market_text = _market_name(market)
    if pe <= low:
        return 90, f"{market_text}市盈率 {_fmt(pe)}，处于偏低区间"
    if pe <= fair:
        return 70, f"{market_text}市盈率 {_fmt(pe)}，估值相对合理"
    if pe <= high:
        return 50, f"{market_text}市盈率 {_fmt(pe)}，估值偏高"
    if pe <= extreme:
        return 30, f"{market_text}市盈率 {_fmt(pe)}，估值明显偏高"
    return 15, f"市盈率 {_fmt(pe)}，估值明显偏高"


def _score_pb(pb: float, market: Optional[Market]):
    if pb <= 0:
        return 50, f"市净率 {_fmt(pb)}，异常，估值中性"
    low, fair, high, extreme = _PB_RULES.get(market, _PB_RULES[Market.A_SHARE])
    market_text = _market_name(market)
    if pb <= low:
        return 85, f"{market_text}市净率 {_fmt(pb)}，处于偏低区间"
    if pb <= fair:
        return 65, f"{market_text}市净率 {_fmt(pb)}，估值相对合理"
    if pb <= high:
        return 45, f"{market_text}市净率 {_fmt(pb)}，估值偏高"
    if pb <= extreme:
        return 30, f"{market_text}市净率 {_fmt(pb)}，估值明显偏高"
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


def analyze(fundamentals: Fundamentals, market: Optional[Market] = None) -> ValueResult:
    normalized = {
        "pe_ttm": _normalize_value(fundamentals.pe_ttm),
        "pb": _normalize_value(fundamentals.pb),
        "roe": _normalize_value(fundamentals.roe),
        "dividend_yield": _normalize_value(fundamentals.dividend_yield),
        "revenue_growth": _normalize_value(fundamentals.revenue_growth),
        "profit_growth": _normalize_value(fundamentals.profit_growth),
    }
    missing = [name for name, value in normalized.items() if value is None]
    available_count = len(normalized) - len(missing)
    confidence = round(available_count / len(normalized), 2)
    data_warnings = [
        "缺少基本面字段：" + "、".join(_METRIC_LABELS[k] for k in missing)
    ] if missing else []

    if all(v is None for v in normalized.values()):
        return ValueResult(
            score=50,
            label="基本面数据不可用",
            signals=["基本面数据不可用，无法进行价值评估"],
            details=normalized,
            confidence=0.0,
            data_warnings=data_warnings,
            interpretation="基本面数据缺失，综合结论应主要参考技术面且降低可信度。",
        )

    scores: List[float] = []
    signals: List[str] = []

    if normalized["pe_ttm"] is not None:
        s, sig = _score_pe(normalized["pe_ttm"], market)
        scores.append(s)
        signals.append(sig)

    if normalized["pb"] is not None:
        s, sig = _score_pb(normalized["pb"], market)
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

    if confidence < 0.5:
        interpretation = "基本面字段不足，当前估值判断可信度偏低。"
    elif score >= 75:
        interpretation = "基本面相对占优，但仍需结合趋势和风险信号确认。"
    elif score >= 40:
        interpretation = "基本面没有明显单边优势，适合作为中性参考。"
    else:
        interpretation = "基本面估值或盈利质量偏弱，需控制预期。"

    return ValueResult(
        score=score,
        label=label,
        signals=signals,
        details=normalized,
        confidence=confidence,
        data_warnings=data_warnings,
        interpretation=interpretation,
    )
