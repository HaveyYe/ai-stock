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
        score = 85
        label = "黄金支撑区"
        signals = ["价格处于斐波那契 50%-61.8% 黄金支撑区，看多"]
    elif 0.382 <= p < 0.5:
        score = 70
        label = "偏支撑区"
        signals = ["价格接近 38.2% 回撤位，下方支撑较强"]
    elif 0.618 < p <= 0.786:
        score = 65
        label = "支撑区下沿"
        signals = ["价格在 61.8%-78.6% 区间，仍处支撑带"]
    elif 0.236 <= p < 0.382:
        score = 50
        label = "中段"
        signals = ["价格处于 23.6%-38.2% 中段，方向不明"]
    elif 0 <= p < 0.236:
        score = 40
        label = "接近前高"
        signals = ["价格接近 0% 回撤位（前高），上行阻力增大"]
    elif 0.786 < p <= 1.0:
        score = 35
        label = "接近前高"
        signals = ["价格在 78.6% 以上，接近前高，谨慎追高"]
    elif p > 1.0:
        score = 25
        label = "突破前高"
        signals = ["价格突破区间高点（0%），追高风险"]
    else:
        score = 20
        label = "跌破前低"
        signals = ["价格跌破区间低点（100%），弱势"]

    nearest_level = min(levels.values(), key=lambda lv: abs(lv - current_price))
    pct = round((current_price - nearest_level) / nearest_level * 100, 1)
    signals.append(
        f"当前价 {round(current_price, 2)}，距最近关键位偏差 {pct}%..."
    )

    score = int(round(score))

    return FibonacciResult(
        score=score,
        levels=levels,
        swing_high=swing_high,
        swing_low=swing_low,
        current_price=current_price,
        position_ratio=position_ratio,
        label=label,
        signals=signals,
    )
