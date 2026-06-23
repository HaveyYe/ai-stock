from typing import Optional

import pandas as pd

from src.types import OptionAnalysisResult


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(f):
        return None
    return f


def _sum_col(df: pd.DataFrame, col: str) -> float:
    if df is None or df.empty or col not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[col], errors="coerce").fillna(0).sum())


def _median_iv(calls: pd.DataFrame, puts: pd.DataFrame) -> Optional[float]:
    values = []
    for df in (calls, puts):
        if df is not None and not df.empty and "impliedVolatility" in df.columns:
            values.extend(pd.to_numeric(df["impliedVolatility"], errors="coerce").dropna().tolist())
    if not values:
        return None
    median = float(pd.Series(values).median())
    return median * 100 if median <= 3 else median


def _activity_strike(df: pd.DataFrame, current_price: Optional[float], side: str) -> Optional[float]:
    if df is None or df.empty or "strike" not in df.columns:
        return None
    work = df.copy()
    work["strike"] = pd.to_numeric(work["strike"], errors="coerce")
    work["volume"] = pd.to_numeric(work.get("volume", 0), errors="coerce").fillna(0)
    work["openInterest"] = pd.to_numeric(work.get("openInterest", 0), errors="coerce").fillna(0)
    work["activity"] = work["volume"] + work["openInterest"]
    work = work.dropna(subset=["strike"])
    if current_price is not None:
        if side == "put":
            filtered = work[work["strike"] <= current_price]
        else:
            filtered = work[work["strike"] >= current_price]
        if not filtered.empty:
            work = filtered
    if work.empty:
        return None
    return _to_float(work.sort_values("activity", ascending=False)["strike"].iloc[0])


def _ratio(numerator: float, denominator: float) -> Optional[float]:
    if denominator <= 0:
        return None
    return numerator / denominator


def unavailable(reason: str) -> OptionAnalysisResult:
    return OptionAnalysisResult(
        available=False,
        score=50,
        label="期权数据不可用",
        warnings=[reason],
        confidence=0.0,
        interpretation="期权维度暂不参与综合评分。",
    )


def analyze(
    calls: pd.DataFrame,
    puts: pd.DataFrame,
    current_price: Optional[float] = None,
    expiry: Optional[str] = None,
) -> OptionAnalysisResult:
    if (calls is None or calls.empty) and (puts is None or puts.empty):
        return unavailable("未获取到可用期权链")

    call_volume = _sum_col(calls, "volume")
    put_volume = _sum_col(puts, "volume")
    call_oi = _sum_col(calls, "openInterest")
    put_oi = _sum_col(puts, "openInterest")

    pcr_volume = _ratio(put_volume, call_volume)
    pcr_oi = _ratio(put_oi, call_oi)
    median_iv = _median_iv(calls, puts)
    support = _activity_strike(puts, current_price, "put")
    resistance = _activity_strike(calls, current_price, "call")

    score = 50.0
    signals: list[str] = []
    warnings: list[str] = []

    if pcr_volume is not None:
        if pcr_volume <= 0.7:
            score += 9
            signals.append(f"Put/Call 成交量比 {pcr_volume:.2f}，期权成交偏乐观")
        elif pcr_volume >= 1.3:
            score -= 10
            signals.append(f"Put/Call 成交量比 {pcr_volume:.2f}，避险需求偏强")
        else:
            signals.append(f"Put/Call 成交量比 {pcr_volume:.2f}，情绪中性")
    else:
        warnings.append("成交量不足，无法计算 Put/Call 成交量比")

    if pcr_oi is not None:
        if pcr_oi <= 0.8:
            score += 4
            signals.append(f"Put/Call 持仓比 {pcr_oi:.2f}，持仓结构略偏多")
        elif pcr_oi >= 1.4:
            score -= 5
            signals.append(f"Put/Call 持仓比 {pcr_oi:.2f}，保护性持仓偏多")
        else:
            signals.append(f"Put/Call 持仓比 {pcr_oi:.2f}，持仓结构中性")
    else:
        warnings.append("持仓量不足，无法计算 Put/Call 持仓比")

    if median_iv is not None:
        if median_iv >= 80:
            score -= 6
            signals.append(f"近月隐含波动率中位数 {median_iv:.1f}%，波动预期偏高")
        elif median_iv <= 25:
            score += 3
            signals.append(f"近月隐含波动率中位数 {median_iv:.1f}%，波动预期相对温和")
        else:
            signals.append(f"近月隐含波动率中位数 {median_iv:.1f}%")
    else:
        warnings.append("隐含波动率字段不可用")

    if support is not None:
        signals.append(f"Put 活跃行权价 {support:.2f} 可作为期权支撑参考")
    if resistance is not None:
        signals.append(f"Call 活跃行权价 {resistance:.2f} 可作为期权压力参考")

    score = round(max(0.0, min(100.0, score)))
    if score >= 62:
        label = "期权情绪偏积极"
        interpretation = "近月期权成交和持仓对价格偏正面，但仍需结合正股量价确认。"
    elif score <= 42:
        label = "期权风险偏高"
        interpretation = "期权市场体现出更强避险或波动预期，短线风险需要提高权重。"
    else:
        label = "期权情绪中性"
        interpretation = "期权维度未形成明确方向，主要作为支撑压力和风险补充。"

    confidence = 0.72
    if warnings:
        confidence -= min(0.32, len(warnings) * 0.1)

    return OptionAnalysisResult(
        available=True,
        score=score,
        label=label,
        expiry=expiry,
        put_call_volume_ratio=pcr_volume,
        put_call_open_interest_ratio=pcr_oi,
        median_iv=median_iv,
        support_strike=support,
        resistance_strike=resistance,
        max_put_strike=support,
        max_call_strike=resistance,
        signals=signals or ["期权链已获取，但暂无明确情绪信号"],
        warnings=warnings,
        confidence=round(max(0.0, min(1.0, confidence)), 2),
        interpretation=interpretation,
    )
