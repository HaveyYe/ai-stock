from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd


@dataclass
class PriceActionResult:
    score: float
    label: str = ""
    trend: str = ""
    support: Optional[float] = None
    resistance: Optional[float] = None
    current_price: float = 0.0
    range_position: float = 0.0
    breakout_state: str = ""
    body_ratio: float = 0.0
    volume_ratio: Optional[float] = None
    signals: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    confidence: float = 1.0
    data_warnings: List[str] = field(default_factory=list)
    interpretation: str = ""


def _safe_float(value, default: float = 0.0) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(f):
        return default
    return f


def _last_swing_high(highs: pd.Series, lookback: int = 3) -> Optional[float]:
    if len(highs) < lookback * 2 + 1:
        return None
    values = highs.reset_index(drop=True)
    for idx in range(len(values) - lookback - 1, lookback - 1, -1):
        center = values.iloc[idx]
        window = values.iloc[idx - lookback:idx + lookback + 1]
        if center == window.max():
            return _safe_float(center)
    return None


def _last_swing_low(lows: pd.Series, lookback: int = 3) -> Optional[float]:
    if len(lows) < lookback * 2 + 1:
        return None
    values = lows.reset_index(drop=True)
    for idx in range(len(values) - lookback - 1, lookback - 1, -1):
        center = values.iloc[idx]
        window = values.iloc[idx - lookback:idx + lookback + 1]
        if center == window.min():
            return _safe_float(center)
    return None


def _trend_from_structure(close: pd.Series) -> tuple[str, float]:
    if len(close) < 20:
        return "样本不足", 50.0

    ma_short = close.tail(10).mean()
    ma_mid = close.tail(20).mean()
    recent = close.tail(5).mean()
    previous = close.iloc[-20:-10].mean()
    latest = close.iloc[-1]

    if latest > ma_short > ma_mid and recent > previous:
        return "上升结构", 74.0
    if latest < ma_short < ma_mid and recent < previous:
        return "下降结构", 28.0
    if latest >= ma_mid and recent >= previous:
        return "偏强震荡", 58.0
    if latest <= ma_mid and recent <= previous:
        return "偏弱震荡", 42.0
    return "区间震荡", 50.0


def analyze(klines, window: int = 60) -> PriceActionResult:
    if klines is None or not isinstance(klines, pd.DataFrame) or klines.empty:
        raise ValueError("K线数据不足，无法进行 Price Action 分析")

    required = {"open", "high", "low", "close"}
    if not required.issubset(set(klines.columns)):
        raise ValueError("K线数据缺少 open/high/low/close 列")

    df = klines.tail(window).copy()
    if len(df) < 20:
        raise ValueError("K线数据不足以识别价格行为（需至少 20 行）")

    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    open_ = df["open"].astype(float)
    volume = df["volume"].astype(float) if "volume" in df.columns else None

    current = _safe_float(close.iloc[-1])
    support = _last_swing_low(low) or _safe_float(low.tail(20).min())
    resistance = _last_swing_high(high) or _safe_float(high.tail(20).max())
    recent_high = _safe_float(high.iloc[:-1].tail(20).max())
    recent_low = _safe_float(low.iloc[:-1].tail(20).min())

    if resistance == support:
        range_position = 0.5
    else:
        range_position = (current - support) / (resistance - support)

    trend, score = _trend_from_structure(close)
    signals: List[str] = [f"价格结构：{trend}"]
    risks: List[str] = []

    breakout_state = "区间内"
    if current > recent_high * 1.005:
        breakout_state = "向上突破"
        score += 12
        signals.append(f"收盘价突破近 20 日高点 {recent_high:.2f}，突破有效性需看量能和回踩")
    elif current < recent_low * 0.995:
        breakout_state = "向下跌破"
        score -= 14
        risks.append(f"收盘价跌破近 20 日低点 {recent_low:.2f}，结构转弱")
    elif range_position >= 0.82:
        breakout_state = "接近压力"
        score -= 5
        risks.append("价格接近近期压力区，追高性价比下降")
    elif range_position <= 0.18:
        breakout_state = "接近支撑"
        score += 5
        signals.append("价格接近近期支撑区，适合观察企稳或反弹确认")

    last_open = _safe_float(open_.iloc[-1])
    last_high = _safe_float(high.iloc[-1])
    last_low = _safe_float(low.iloc[-1])
    day_range = max(last_high - last_low, 0.0)
    body = abs(current - last_open)
    body_ratio = body / day_range if day_range else 0.0
    upper_shadow = last_high - max(current, last_open)
    lower_shadow = min(current, last_open) - last_low

    if day_range > 0:
        if current > last_open and body_ratio >= 0.6:
            score += 6
            signals.append("最新 K 线为强实体阳线，短线买盘主动性较强")
        elif current < last_open and body_ratio >= 0.6:
            score -= 8
            risks.append("最新 K 线为强实体阴线，短线抛压较重")
        if upper_shadow / day_range >= 0.45:
            score -= 6
            risks.append("最新 K 线上影线较长，上方抛压明显")
        if lower_shadow / day_range >= 0.45:
            score += 5
            signals.append("最新 K 线下影线较长，下方承接出现")

    volume_ratio = None
    if volume is not None and len(volume.dropna()) >= 21:
        avg_volume = volume.iloc[:-1].tail(20).mean()
        latest_volume = volume.iloc[-1]
        if avg_volume and not pd.isna(avg_volume):
            volume_ratio = float(latest_volume / avg_volume)
            if breakout_state == "向上突破" and volume_ratio >= 1.3:
                score += 7
                signals.append(f"突破伴随放量（量比 {volume_ratio:.2f}），确认度提升")
            elif breakout_state == "向上突破":
                score -= 5
                risks.append(f"突破量能不足（量比 {volume_ratio:.2f}），存在假突破风险")
            elif breakout_state == "向下跌破" and volume_ratio >= 1.2:
                score -= 5
                risks.append(f"跌破伴随放量（量比 {volume_ratio:.2f}），风险确认度提升")

    data_warnings: List[str] = []
    if len(klines) < window:
        data_warnings.append(f"Price Action 样本少于 {window} 日，结构判断参考性降低")
    if volume is None:
        data_warnings.append("缺少成交量字段，量价确认不可用")

    score = round(max(0.0, min(100.0, score)))
    confidence = 0.88
    if data_warnings:
        confidence -= 0.18
    if breakout_state in {"向上突破", "向下跌破"} and volume_ratio is None:
        confidence -= 0.12
    confidence = round(max(0.0, min(1.0, confidence)), 2)

    if score >= 70:
        label = "价格行为偏强"
        interpretation = "趋势结构和短线行为偏积极，但突破后仍需观察回踩和量能延续。"
    elif score >= 55:
        label = "结构偏积极"
        interpretation = "价格行为略偏积极，适合继续跟踪确认信号。"
    elif score >= 40:
        label = "区间震荡"
        interpretation = "价格行为未形成单边共振，宜等待突破或支撑确认。"
    else:
        label = "价格行为偏弱"
        interpretation = "价格结构偏弱或跌破关键区间，短线风险高于机会。"

    if not signals:
        signals.append("暂无明确价格行为信号")

    return PriceActionResult(
        score=score,
        label=label,
        trend=trend,
        support=support,
        resistance=resistance,
        current_price=current,
        range_position=range_position,
        breakout_state=breakout_state,
        body_ratio=body_ratio,
        volume_ratio=volume_ratio,
        signals=signals,
        risks=risks,
        confidence=confidence,
        data_warnings=data_warnings,
        interpretation=interpretation,
    )
