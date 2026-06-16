from typing import Optional

from src import config
from src.types import DataQuality, Fundamentals, StockInfo
from src.analyzers.value_analyzer import ValueResult
from src.analyzers.bollinger_analyzer import BollingerResult
from src.analyzers.fibonacci_analyzer import FibonacciResult
from src.analyzers.price_action_analyzer import PriceActionResult
from src.scoring.composer import CompositeResult


_MARKET_CN = {
    "a_share": "A股",
    "hk": "港股",
    "us": "美股",
}

_FIB_LEVELS = [
    (0.0, "0.0%"),
    (0.236, "23.6%"),
    (0.382, "38.2%"),
    (0.5, "50.0%"),
    (0.618, "61.8%"),
    (0.786, "78.6%"),
    (1.0, "100.0%"),
]

_ACTION_TIPS = {
    "机会关注": "当前仅代表机会值得跟踪，仍需确认趋势和控制仓位。",
    "谨慎观察": "等待趋势或估值更明朗后再行决策。",
    "中性观察": "保持观察，避免在信号不共振时激进参与。",
    "风险回避": "风险信号占优，等待更好时机。",
}


def _fmt_num(value, suffix: str = "") -> str:
    if value is None:
        return "数据不可用"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return "数据不可用"
    text = f"{f:.2f}"
    return f"{text}{suffix}"


def _market_cn(info: StockInfo) -> str:
    market = getattr(info, "market", None)
    if market is None:
        return "未知"
    value = getattr(market, "value", None)
    return _MARKET_CN.get(value, "未知")


def _fmt_signals(signals) -> str:
    if not signals:
        return "  - 暂无"
    return "\n".join(f"  - {s}" for s in signals)


def _action_tip(action: str) -> str:
    return _ACTION_TIPS.get(action, "请结合自身风险承受能力谨慎决策。")


def build_report(
    info: StockInfo,
    fundamentals: Fundamentals,
    value_result: ValueResult,
    bollinger_result: BollingerResult,
    fibonacci_result: FibonacciResult,
    price_action_result: PriceActionResult,
    composite_result: CompositeResult,
    data_quality: Optional[DataQuality] = None,
) -> str:
    name = getattr(info, "name", "")
    code = getattr(info, "code", "")
    market_cn = _market_cn(info)

    score = getattr(composite_result, "score", 0)
    action = getattr(composite_result, "action", "")
    action_en = getattr(composite_result, "action_en", "")
    breakdown = getattr(composite_result, "breakdown", {}) or {}
    weights = getattr(composite_result, "weights", {}) or {}
    confidence = getattr(composite_result, "confidence", 1.0)
    risk_level = getattr(composite_result, "risk_level", "中")
    summary = getattr(composite_result, "summary", "")
    conflicts = getattr(composite_result, "conflicts", []) or getattr(composite_result, "signal_conflicts", []) or []

    v_score = breakdown.get("value", 0)
    b_score = breakdown.get("bollinger", 0)
    f_score = breakdown.get("fibonacci", 0)
    p_score = breakdown.get("price_action", 0)
    w_value = float(weights.get("value", 0.0))
    w_bollinger = float(weights.get("bollinger", 0.0))
    w_fibonacci = float(weights.get("fibonacci", 0.0))
    w_price_action = float(weights.get("price_action", 0.0))

    pe = getattr(fundamentals, "pe_ttm", None)
    pb = getattr(fundamentals, "pb", None)
    roe = getattr(fundamentals, "roe", None)
    dy = getattr(fundamentals, "dividend_yield", None)
    rg = getattr(fundamentals, "revenue_growth", None)
    pg = getattr(fundamentals, "profit_growth", None)

    value_label = getattr(value_result, "label", "")
    bollinger_label = getattr(bollinger_result, "label", "")
    fibonacci_label = getattr(fibonacci_result, "label", "")
    price_action_label = getattr(price_action_result, "label", "")

    upper = getattr(bollinger_result, "upper", None)
    middle = getattr(bollinger_result, "middle", None)
    lower = getattr(bollinger_result, "lower", None)
    percent_b = getattr(bollinger_result, "percent_b", None)
    bandwidth = getattr(bollinger_result, "bandwidth", None)
    bandwidth_percentile = getattr(bollinger_result, "bandwidth_percentile", None)

    swing_high = getattr(fibonacci_result, "swing_high", None)
    swing_low = getattr(fibonacci_result, "swing_low", None)
    current_price = getattr(fibonacci_result, "current_price", None)
    position_ratio = getattr(fibonacci_result, "position_ratio", None)
    levels = getattr(fibonacci_result, "levels", {}) or {}
    pa_support = getattr(price_action_result, "support", None)
    pa_resistance = getattr(price_action_result, "resistance", None)
    pa_current = getattr(price_action_result, "current_price", None)
    pa_trend = getattr(price_action_result, "trend", "")
    pa_state = getattr(price_action_result, "breakout_state", "")
    pa_range_position = getattr(price_action_result, "range_position", None)
    pa_body_ratio = getattr(price_action_result, "body_ratio", None)
    pa_volume_ratio = getattr(price_action_result, "volume_ratio", None)

    lines = []

    lines.append(f"# {name} ({code}) 分析报告")
    lines.append("")
    lines.append(
        f"**市场**：{market_cn}  **综合评分**：{score}/100  "
        f"**结论**：{action}（{action_en}）  "
        f"**置信度**：{float(confidence) * 100:.0f}%  **风险等级**：{risk_level}"
    )
    if summary:
        lines.append("")
        lines.append(f"**结论摘要**：{summary}")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 一、综合评分")
    lines.append(
        f"- 价值分析：{v_score} 分（权重 {w_value * 100:.0f}%）"
    )
    lines.append(
        f"- 布林带：{b_score} 分（权重 {w_bollinger * 100:.0f}%）"
    )
    lines.append(
        f"- 斐波那契：{f_score} 分（权重 {w_fibonacci * 100:.0f}%）"
    )
    lines.append(
        f"- Price Action：{p_score} 分（权重 {w_price_action * 100:.0f}%）"
    )
    lines.append(f"- **加权综合分：{score} → {action}**")
    lines.append(f"- 综合置信度：{float(confidence) * 100:.0f}%")
    lines.append(f"- 风险等级：{risk_level}")
    if conflicts:
        lines.append("- 冲突信号：")
        lines.extend(f"  - {item}" for item in conflicts)
    else:
        lines.append("- 冲突信号：暂无明显冲突")
    if data_quality is not None:
        missing = "、".join(data_quality.missing_fundamentals) if data_quality.missing_fundamentals else "无"
        warnings = data_quality.warnings or []
        lines.append("- 数据质量：")
        lines.append(f"  - 完整度：{data_quality.completeness * 100:.0f}%")
        lines.append(f"  - 行情样本：{data_quality.kline_days} 日")
        lines.append(f"  - 最新交易日：{data_quality.latest_trade_date or '数据不可用'}")
        lines.append(f"  - 缺失基本面字段：{missing}")
        if warnings:
            lines.append("  - 数据提示：" + "；".join(warnings))
    lines.append("")

    lines.append(f"## 二、价值分析（{value_label}）")
    lines.append(f"- 市盈率 PE(TTM)：{_fmt_num(pe)}")
    lines.append(f"- 市净率 PB：{_fmt_num(pb)}")
    lines.append(f"- ROE：{_fmt_num(roe, '%')}")
    lines.append(f"- 股息率：{_fmt_num(dy, '%')}")
    lines.append(f"- 营收同比增长：{_fmt_num(rg, '%')}")
    lines.append(f"- 净利润同比增长：{_fmt_num(pg, '%')}")
    lines.append(f"- 置信度：{float(getattr(value_result, 'confidence', 1.0)) * 100:.0f}%")
    if getattr(value_result, "interpretation", ""):
        lines.append(f"- 解读：{value_result.interpretation}")
    lines.append("- 信号解读：")
    lines.append(_fmt_signals(getattr(value_result, "signals", [])))
    lines.append("")

    lines.append(f"## 三、技术形态 - 布林带（{bollinger_label}）")
    lines.append(
        f"- 上轨 / 中轨 / 下轨：{_fmt_num(upper)} / {_fmt_num(middle)} / {_fmt_num(lower)}"
    )
    lines.append(
        f"- %B 指标：{_fmt_num(percent_b)}（>1 超买，<0 超卖）"
    )
    bw_text = _fmt_num(bandwidth)
    if bandwidth_percentile is None:
        bw_full = f"{bw_text}，历史分位 数据不可用"
    else:
        bw_full = f"{bw_text}，历史分位 {float(bandwidth_percentile) * 100:.0f}%"
    lines.append(f"- 带宽：{bw_full}")
    lines.append(f"- 置信度：{float(getattr(bollinger_result, 'confidence', 1.0)) * 100:.0f}%")
    if getattr(bollinger_result, "interpretation", ""):
        lines.append(f"- 解读：{bollinger_result.interpretation}")
    lines.append("- 信号解读：")
    lines.append(_fmt_signals(getattr(bollinger_result, "signals", [])))
    lines.append("")

    lines.append(f"## 四、技术形态 - 斐波那契（{fibonacci_label}）")
    lines.append(
        f"- 近 {config.FIBONACCI_WINDOW} 日最高 / 最低："
        f"{_fmt_num(swing_high)} / {_fmt_num(swing_low)}"
    )
    if position_ratio is None:
        pos_text = "数据不可用"
    else:
        pos_text = f"{float(position_ratio) * 100:.1f}%"
    lines.append(
        f"- 当前价：{_fmt_num(current_price)}（位于 {pos_text} 回撤位）"
    )
    lines.append("- 关键回撤位：")
    for ratio, label in _FIB_LEVELS:
        price = levels.get(ratio, None)
        lines.append(f"  - {label} → {_fmt_num(price)}")
    lines.append(f"- 置信度：{float(getattr(fibonacci_result, 'confidence', 1.0)) * 100:.0f}%")
    if getattr(fibonacci_result, "interpretation", ""):
        lines.append(f"- 解读：{fibonacci_result.interpretation}")
    lines.append("- 信号解读：")
    lines.append(_fmt_signals(getattr(fibonacci_result, "signals", [])))
    lines.append("")

    lines.append(f"## 五、Price Action（{price_action_label}）")
    lines.append(f"- 当前价：{_fmt_num(pa_current)}")
    lines.append(f"- 价格结构：{pa_trend or '数据不可用'}")
    lines.append(f"- 支撑 / 压力：{_fmt_num(pa_support)} / {_fmt_num(pa_resistance)}")
    if pa_range_position is None:
        pa_pos_text = "数据不可用"
    else:
        pa_pos_text = f"{float(pa_range_position) * 100:.1f}%"
    lines.append(f"- 区间位置：{pa_pos_text}")
    lines.append(f"- 突破状态：{pa_state or '数据不可用'}")
    lines.append(f"- 实体占比：{_fmt_num(pa_body_ratio)}")
    lines.append(f"- 成交量确认：{_fmt_num(pa_volume_ratio)}")
    lines.append(f"- 置信度：{float(getattr(price_action_result, 'confidence', 1.0)) * 100:.0f}%")
    if getattr(price_action_result, "interpretation", ""):
        lines.append(f"- 解读：{price_action_result.interpretation}")
    lines.append("- 信号解读：")
    lines.append(_fmt_signals(getattr(price_action_result, "signals", [])))
    lines.append("- 风险提示：")
    lines.append(_fmt_signals(getattr(price_action_result, "risks", [])))
    lines.append("")

    lines.append("## 六、风险提示")
    lines.append("- 本报告由程序根据公开数据自动生成，仅供参考，不构成投资建议。")
    lines.append("- 技术指标存在滞后性，请结合宏观环境与公司基本面综合判断。")
    lines.append(f"- {_action_tip(action)}")

    return "\n".join(lines)
