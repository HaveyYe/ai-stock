from dataclasses import dataclass, field
from typing import Dict, List

import pandas as pd

from src import config


@dataclass
class FibonacciResult:
    score: float
    levels: Dict[float, float] = field(default_factory=dict)
    swing_high: float = 0.0
    swing_low: float = 0.0
    current_price: float = 0.0
    position_ratio: float = 0.0
    label: str = ""
    signals: List[str] = field(default_factory=list)
    confidence: float = 1.0
    data_warnings: List[str] = field(default_factory=list)
    interpretation: str = ""


def analyze(klines, window=None) -> FibonacciResult:
    if window is None:
        window = config.FIBONACCI_WINDOW

    if (
        klines is None
        or not isinstance(klines, pd.DataFrame)
        or klines.empty
    ):
        raise ValueError("K线数据不足，无法进行斐波那契分析")

    required_columns = {"high", "low", "close"}
    if not required_columns.issubset(set(klines.columns)):
        raise ValueError("K线数据不足，无法进行斐波那契分析")

    df = klines.tail(window) if window else klines
    if df.empty:
        raise ValueError("K线数据不足，无法进行斐波那契分析")

    swing_high = float(df["high"].max())
    swing_low = float(df["low"].min())
    current_price = float(df["close"].iloc[-1])

    ratios = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    levels: Dict[float, float] = {}
    for r in ratios:
        level_price = swing_low + (swing_high - swing_low) * r
        levels[r] = round(float(level_price), 4)

    if swing_high == swing_low:
        position_ratio = 0.5
    else:
        position_ratio = (current_price - swing_low) / (swing_high - swing_low)

    p = position_ratio
    if 0.5 <= p <= 0.618:
        score = 66
        label = "黄金区观察"
        signals = ["价格处于斐波那契 50%-61.8% 区间，存在支撑观察价值"]
    elif 0.382 <= p < 0.5:
        score = 60
        label = "偏支撑区"
        signals = ["价格接近 38.2% 区间，下方支撑需结合量价确认"]
    elif 0.618 < p <= 0.786:
        score = 58
        label = "上方压力区"
        signals = ["价格在 61.8%-78.6% 区间，接近区间上沿，追高性价比下降"]
    elif 0.236 <= p < 0.382:
        score = 50
        label = "中段"
        signals = ["价格处于 23.6%-38.2% 中段，方向不明"]
    elif 0 <= p < 0.236:
        score = 42
        label = "接近区间低位"
        signals = ["价格接近区间低位，反弹空间存在但弱势风险仍高"]
    elif 0.786 < p <= 1.0:
        score = 36
        label = "接近前高"
        signals = ["价格在 78.6% 以上，接近区间高位，谨慎追高"]
    elif p > 1.0:
        score = 44
        label = "突破前高"
        signals = ["价格突破区间高点，需观察突破有效性，追高风险同步上升"]
    else:
        score = 20
        label = "跌破前低"
        signals = ["价格跌破区间低点，弱势风险较高"]

    nearest_level = min(levels.values(), key=lambda lv: abs(lv - current_price))
    pct = round((current_price - nearest_level) / nearest_level * 100, 1)
    signals.append(
        f"当前价 {round(current_price, 2)}，距最近关键位偏差 {pct}%..."
    )

    score = int(round(score))
    data_warnings: List[str] = []
    if len(klines) < window:
        data_warnings.append(f"斐波那契样本少于 {window} 日，区间高低点稳定性不足")
    if swing_high == swing_low:
        data_warnings.append("区间高低点相同，斐波那契位置参考性降低")

    confidence = 0.85 if not data_warnings else 0.6
    if p < 0:
        interpretation = "价格跌破观察区间，斐波那契支撑已失效。"
    elif p > 1:
        interpretation = "价格突破观察区间，需用成交量和回踩确认突破有效性。"
    elif 0.5 <= p <= 0.618:
        interpretation = "价格位于常见回撤观察区，但只代表位置优势，不代表趋势已反转。"
    elif p >= 0.786:
        interpretation = "价格接近区间高位，收益风险比下降。"
    else:
        interpretation = "价格位于区间内部，斐波那契给出的方向信号有限。"

    return FibonacciResult(
        score=score,
        levels=levels,
        swing_high=swing_high,
        swing_low=swing_low,
        current_price=current_price,
        position_ratio=position_ratio,
        label=label,
        signals=signals,
        confidence=confidence,
        data_warnings=data_warnings,
        interpretation=interpretation,
    )
