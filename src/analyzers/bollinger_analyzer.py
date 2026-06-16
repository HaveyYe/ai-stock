from dataclasses import dataclass, field
from typing import List

import pandas as pd

from src import config


@dataclass
class BollingerResult:
    score: float
    upper: float = 0.0
    middle: float = 0.0
    lower: float = 0.0
    percent_b: float = 0.0
    bandwidth: float = 0.0
    bandwidth_percentile: float = 0.0
    label: str = ""
    signals: List[str] = field(default_factory=list)
    confidence: float = 1.0
    data_warnings: List[str] = field(default_factory=list)
    interpretation: str = ""


def analyze(klines, window=None, num_std=None) -> BollingerResult:
    if window is None:
        window = config.BOLLINGER_WINDOW
    if num_std is None:
        num_std = config.BOLLINGER_NUM_STD

    if klines is None or "close" not in klines.columns:
        raise ValueError("K线数据缺少 close 列")

    if len(klines) < window:
        raise ValueError(f"K线数据不足以计算布林带（需至少 {window} 行）")

    close = klines["close"]
    mid = close.rolling(window).mean()
    std = close.rolling(window).std(ddof=0)
    upper = mid + num_std * std
    lower = mid - num_std * std

    band_width = upper - lower
    percent_b_series = (close - lower) / band_width
    bandwidth_series = band_width / mid

    percent_b_series = percent_b_series.where(band_width != 0, 0.5)

    last_mid = mid.iloc[-1]
    last_upper = upper.iloc[-1]
    last_lower = lower.iloc[-1]

    if pd.isna(last_mid) or pd.isna(last_upper) or pd.isna(last_lower):
        raise ValueError(f"K线数据不足以计算布林带（需至少 {window} 行）")

    last_percent_b = percent_b_series.iloc[-1]
    last_bandwidth = bandwidth_series.iloc[-1]

    hist = bandwidth_series.tail(config.FIBONACCI_WINDOW).dropna()
    if len(hist) > 0 and not pd.isna(last_bandwidth):
        bandwidth_percentile = float((hist <= last_bandwidth).mean())
    else:
        bandwidth_percentile = 0.0

    pb = float(last_percent_b)
    latest_close = float(close.iloc[-1])
    recent_close = close.tail(min(len(close), 5))
    recent_return = 0.0
    if len(recent_close) >= 2 and recent_close.iloc[0] != 0:
        recent_return = float((recent_close.iloc[-1] - recent_close.iloc[0]) / recent_close.iloc[0])

    if pb < 0:
        score = 68
        label = "超卖反弹观察"
        signals = [f"收盘价跌破布林带下轨（%B={pb:.2f}），存在反弹机会但趋势仍需确认"]
    elif pb <= 0.2:
        score = 62
        label = "接近下轨"
        signals = [f"%B={pb:.2f}，贴近下轨，偏超卖，适合观察企稳信号"]
    elif pb < 0.8:
        score = 50
        label = "中性区间"
        signals = [f"%B={pb:.2f}，处于布林带中轨附近，中性"]
    elif pb <= 1.0:
        score = 38
        label = "接近上轨"
        signals = [f"%B={pb:.2f}，贴近上轨，偏超买"]
    else:
        score = 28
        label = "超买"
        signals = [f"收盘价突破布林带上轨（%B={pb:.2f}），超买，谨慎"]

    if latest_close < float(last_mid) and recent_return < -0.02:
        score = max(0, score - 8)
        signals.append("短期价格位于中轨下方且近期走弱，超跌信号不等同于趋势反转")
    elif latest_close > float(last_mid) and recent_return > 0.02:
        signals.append("短期价格位于中轨上方且近期走强，动量仍偏积极")

    if bandwidth_percentile <= 0.2:
        signals.append(
            f"带宽收缩（分位 {bandwidth_percentile * 100:.0f}%），变盘临近"
        )

    data_warnings: List[str] = []
    if len(klines) < config.FIBONACCI_WINDOW:
        data_warnings.append(f"布林带历史样本少于 {config.FIBONACCI_WINDOW} 日，带宽分位参考性降低")
    if pd.isna(last_bandwidth) or last_bandwidth == 0:
        data_warnings.append("布林带宽度异常，%B 参考性降低")

    confidence = 0.9 if not data_warnings else 0.65
    if pb < 0 or pb > 1:
        interpretation = "价格位于布林带外侧，代表短线极端位置，需等待回到通道内确认。"
    elif pb <= 0.2:
        interpretation = "价格贴近下轨，偏反弹观察，不应单独视为买入信号。"
    elif pb >= 0.8:
        interpretation = "价格贴近上轨，短线追高风险上升。"
    else:
        interpretation = "价格处于通道中部，布林带方向信号有限。"

    return BollingerResult(
        score=round(score),
        upper=float(last_upper),
        middle=float(last_mid),
        lower=float(last_lower),
        percent_b=pb,
        bandwidth=float(last_bandwidth) if not pd.isna(last_bandwidth) else 0.0,
        bandwidth_percentile=bandwidth_percentile,
        label=label,
        signals=signals,
        confidence=confidence,
        data_warnings=data_warnings,
        interpretation=interpretation,
    )
