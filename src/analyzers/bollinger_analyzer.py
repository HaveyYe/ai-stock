from dataclasses import dataclass, field
from typing import List

import numpy as np
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

    if pb < 0:
        score = 85
        label = "超卖"
        signals = [f"收盘价跌破布林带下轨（%B={pb:.2f}），超卖，关注反弹"]
    elif pb <= 0.2:
        score = 75
        label = "接近下轨"
        signals = [f"%B={pb:.2f}，贴近下轨，偏超卖"]
    elif pb < 0.8:
        score = 50
        label = "中性区间"
        signals = [f"%B={pb:.2f}，处于布林带中轨附近，中性"]
    elif pb <= 1.0:
        score = 30
        label = "接近上轨"
        signals = [f"%B={pb:.2f}，贴近上轨，偏超买"]
    else:
        score = 20
        label = "超买"
        signals = [f"收盘价突破布林带上轨（%B={pb:.2f}），超买，谨慎"]

    if bandwidth_percentile <= 0.2:
        signals.append(
            f"带宽收缩（分位 {bandwidth_percentile * 100:.0f}%），变盘临近"
        )

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
    )
