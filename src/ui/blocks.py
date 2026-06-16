from typing import Optional

import plotly.graph_objects as go
import streamlit as st

from src.analyzers.bollinger_analyzer import BollingerResult
from src.analyzers.fibonacci_analyzer import FibonacciResult
from src.analyzers.price_action_analyzer import PriceActionResult
from src.analyzers.value_analyzer import ValueResult
from src.scoring.composer import CompositeResult
from src.types import DataQuality, Fundamentals, KlineResult, StockInfo

_CSS = """
<style>
.aistock-grid { display: grid; gap: 12px; }
.aistock-grid-2 { grid-template-columns: 1fr 1fr; }
.aistock-grid-3 { grid-template-columns: 1fr 1fr 1fr; }

.aistock-cards-row {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 16px;
    align-items: stretch;
}
.aistock-cards-row > .aistock-card {
    height: 100%;
    display: flex;
    flex-direction: column;
}
@media (max-width: 900px) {
    .aistock-cards-row {
        grid-template-columns: 1fr;
    }
}

.aistock-card {
    background: #ffffff;
    border-radius: 14px;
    padding: 18px 18px 14px 18px;
    box-shadow: 0 1px 4px rgba(15,23,42,0.08);
    border-left: 5px solid var(--accent, #10b981);
}
.aistock-card-head {
    display: flex; justify-content: space-between; align-items: flex-start;
    margin-bottom: 12px;
}
.aistock-card-title { font-size: 13px; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.5px; }
.aistock-card-sub { font-size: 11px; color: #94a3b8; margin-top: 2px; }
.aistock-score-chip {
    font-size: 26px; font-weight: 800; line-height: 1;
    padding: 4px 12px; border-radius: 10px; color: #fff;
}
.aistock-card-body { flex: 1; display: flex; flex-direction: column; }

.aistock-stat {
    background: #f8fafc; border-radius: 8px; padding: 8px 10px;
    border: 1px solid #e2e8f0;
}
.aistock-stat-label { font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: 0.4px; }
.aistock-stat-value { font-size: 17px; font-weight: 700; color: #0f172a; margin-top: 2px; }
.aistock-stat-na { color: #cbd5e1; font-weight: 500; }

.aistock-progress {
    width: 100%; height: 8px; background: #e2e8f0; border-radius: 6px; overflow: hidden; position: relative;
}
.aistock-progress-fill { height: 100%; border-radius: 6px; transition: width .4s; }

.aistock-track {
    position: relative; height: 26px; background: linear-gradient(90deg,#fee2e2 0%,#fef3c7 40%,#dbeafe 60%,#dcfce7 100%);
    border-radius: 8px; margin: 6px 0;
}
.aistock-track-zone {
    position: absolute; top: 0; height: 100%; background: rgba(139,92,246,0.18); border: 1px dashed #8b5cf6;
}
.aistock-track-cursor {
    position: absolute; top: -4px; width: 4px; height: 34px; background: #0f172a; border-radius: 3px;
    box-shadow: 0 0 0 2px #fff;
}
.aistock-track-label { font-size: 10px; color: #64748b; display: flex; justify-content: space-between; }

.aistock-signal {
    display: flex; align-items: flex-start; gap: 7px;
    font-size: 12px; color: #475569; padding: 3px 0; line-height: 1.4;
}
.aistock-signal-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; margin-top: 5px; }

.aistock-hero {
    background: linear-gradient(135deg, var(--hero-bg, #f1f5f9) 0%, #ffffff 100%);
    border-radius: 18px; padding: 24px; box-shadow: 0 4px 14px rgba(15,23,42,0.08);
    border: 1px solid #e2e8f0;
}
.aistock-hero-title { font-size: 22px; font-weight: 800; color: #0f172a; }
.aistock-hero-sub { font-size: 13px; color: #64748b; margin-top: 2px; }
.aistock-action-badge {
    display: inline-block; padding: 8px 18px; border-radius: 999px;
    font-size: 18px; font-weight: 700; color: #fff;
}
.aistock-fib-row {
    display: flex; justify-content: space-between; font-size: 11px; color: #475569;
    padding: 2px 0; border-bottom: 1px dotted #e2e8f0;
}
.aistock-fib-row:last-child { border-bottom: none; }
.aistock-fib-golden { color: #8b5cf6; font-weight: 700; }

.aistock-section-label { font-size: 11px; color: #64748b; margin-bottom: 4px; }
.aistock-section-label-bold { font-weight: 600; }
.aistock-legend {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 10px;
    margin: 14px 0 16px 0;
}
.aistock-legend-item {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-left: 5px solid var(--legend-color);
    border-radius: 10px;
    padding: 10px 12px;
    min-height: 84px;
}
.aistock-legend-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    font-weight: 800;
    color: #0f172a;
}
.aistock-legend-dot {
    width: 10px;
    height: 10px;
    border-radius: 999px;
    background: var(--legend-color);
    flex: 0 0 auto;
}
.aistock-legend-range { margin-top: 4px; font-size: 11px; color: #64748b; font-weight: 700; }
.aistock-legend-desc { margin-top: 4px; font-size: 12px; color: #475569; line-height: 1.45; }
@media (max-width: 900px) {
    .aistock-legend {
        grid-template-columns: 1fr 1fr;
    }
}
@media (max-width: 560px) {
    .aistock-legend {
        grid-template-columns: 1fr;
    }
}

.aistock-tech-snapshot {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-left: 5px solid #0ea5e9;
    border-radius: 12px;
    padding: 14px 16px;
    box-shadow: 0 1px 4px rgba(15,23,42,0.08);
    margin-bottom: 14px;
}
.aistock-tech-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 10px;
}
.aistock-tech-title { font-size: 14px; font-weight: 800; color: #0f172a; }
.aistock-tech-date { font-size: 12px; color: #64748b; }
.aistock-tech-grid {
    display: grid;
    grid-template-columns: 1.25fr repeat(6, minmax(0, 1fr));
    gap: 10px;
}
.aistock-tech-item {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 8px 10px;
    min-width: 0;
}
.aistock-tech-label {
    font-size: 10px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    white-space: nowrap;
}
.aistock-tech-value {
    margin-top: 2px;
    font-size: 15px;
    font-weight: 800;
    color: #0f172a;
    overflow-wrap: anywhere;
}
.aistock-tech-main .aistock-tech-value { font-size: 22px; line-height: 1.1; }
.aistock-tech-sub { margin-top: 2px; font-size: 11px; color: #64748b; }
@media (max-width: 1100px) {
    .aistock-tech-grid {
        grid-template-columns: 1fr 1fr 1fr;
    }
}
@media (max-width: 640px) {
    .aistock-tech-grid {
        grid-template-columns: 1fr 1fr;
    }
    .aistock-tech-main {
        grid-column: 1 / -1;
    }
}

[data-testid="stExpander"] {
    border-radius: 14px !important;
    border: 1px solid #e2e8f0 !important;
    box-shadow: 0 1px 4px rgba(15,23,42,0.08) !important;
    overflow: hidden;
}
[data-testid="stExpander"] details {
    border: none !important;
    border-radius: 14px !important;
}
[data-testid="stExpander"] summary {
    font-size: 14px !important;
    font-weight: 600 !important;
    color: #475569 !important;
    padding: 12px 20px !important;
    border-bottom: 1px solid transparent !important;
}
[data-testid="stExpander"] details[open] summary {
    border-bottom: 1px solid #e2e8f0 !important;
}
[data-testid="stExpander"] h1 {
    font-size: 20px; font-weight: 800; color: #0f172a;
    border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; margin-top: 10px;
}
[data-testid="stExpander"] h2 {
    font-size: 15px; font-weight: 700; color: #2563eb;
    margin-top: 18px; margin-bottom: 6px;
    padding-left: 8px; border-left: 3px solid #2563eb;
}
[data-testid="stExpander"] p { font-size: 13px; color: #475569; line-height: 1.6; }
[data-testid="stExpander"] li { font-size: 13px; color: #475569; line-height: 1.9; }
[data-testid="stExpander"] strong { color: #0f172a; font-weight: 700; }
[data-testid="stExpander"] hr { border: none; border-top: 1px solid #e2e8f0; margin: 12px 0; }
</style>
"""


def inject_dashboard_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def _score_color(score: float) -> str:
    if score >= 75:
        return "#16a34a"
    if score >= 60:
        return "#2563eb"
    if score >= 40:
        return "#f59e0b"
    return "#dc2626"


def render_result_legend() -> None:
    items = [
        ("机会关注", "75-100 分", "#16a34a", "多维信号偏积极，可以重点跟踪，但仍要看确认和仓位。"),
        ("谨慎观察", "60-74 分", "#2563eb", "部分维度有机会，确认度不够，适合等待更清晰的量价配合。"),
        ("中性观察", "40-59 分", "#f59e0b", "信号不共振，方向优势有限，保持观察更稳妥。"),
        ("风险回避", "0-39 分", "#dc2626", "风险信号占优或数据可信度不足，不适合激进参与。"),
    ]
    html = ['<div class="aistock-legend">']
    for title, score_range, color, desc in items:
        html.append(
            f'<div class="aistock-legend-item" style="--legend-color:{color};">'
            f'<div class="aistock-legend-title"><span class="aistock-legend-dot"></span>{title}</div>'
            f'<div class="aistock-legend-range">{score_range}</div>'
            f'<div class="aistock-legend-desc">{desc}</div>'
            f'</div>'
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def _fmt(value, suffix: str = "", digits: int = 2, na: str = "—") -> str:
    if value is None:
        return f'<span class="aistock-stat-na">{na}</span>'
    try:
        f = float(value)
    except (TypeError, ValueError):
        return f'<span class="aistock-stat-na">{na}</span>'
    return f"{f:.{digits}f}{suffix}"


def _progress_html(pct: float, color: str) -> str:
    pct = max(0.0, min(100.0, pct))
    return (
        f'<div class="aistock-progress">'
        f'<div class="aistock-progress-fill" style="width:{pct:.1f}%;background:{color};"></div>'
        f'</div>'
    )


def _signal_list(signals, dot_color: str = "#0ea5e9") -> str:
    if not signals:
        return '<div class="aistock-signal"><span class="aistock-signal-dot" style="background:#cbd5e1;"></span>暂无信号</div>'
    items = "".join(
        f'<div class="aistock-signal"><span class="aistock-signal-dot" style="background:{dot_color};"></span>{s}</div>'
        for s in signals
    )
    return items


def _stat_cell(label: str, value_html: str) -> str:
    return (
        f'<div class="aistock-stat">'
        f'<div class="aistock-stat-label">{label}</div>'
        f'<div class="aistock-stat-value">{value_html}</div>'
        f'</div>'
    )


def _stat_grid(cells, cols: int = 2) -> str:
    tmpl = "aistock-grid-2" if cols == 2 else "aistock-grid-3"
    return f'<div class="aistock-grid {tmpl}">' + "".join(cells) + "</div>"


def _plain_number(value, suffix: str = "", digits: int = 2, na: str = "—") -> str:
    if value is None:
        return na
    try:
        f = float(value)
    except (TypeError, ValueError):
        return na
    if f != f:
        return na
    return f"{f:.{digits}f}{suffix}"


def _signed_number(value, suffix: str = "", digits: int = 2, na: str = "—") -> str:
    if value is None:
        return na
    try:
        f = float(value)
    except (TypeError, ValueError):
        return na
    if f != f:
        return na
    return f"{f:+.{digits}f}{suffix}"


def _volume_text(value) -> str:
    if value is None:
        return "—"
    try:
        volume = float(value)
    except (TypeError, ValueError):
        return "—"
    if volume != volume:
        return "—"
    if volume >= 100_000_000:
        return f"{volume / 100_000_000:.2f}亿"
    if volume >= 10_000:
        return f"{volume / 10_000:.2f}万"
    return f"{volume:.0f}"


def _last_trade_date(klines, data_quality: Optional[DataQuality]) -> str:
    if data_quality is not None and data_quality.latest_trade_date:
        return data_quality.latest_trade_date
    if klines is not None and not klines.empty and "date" in klines.columns:
        latest = klines["date"].iloc[-1]
        return latest.strftime("%Y-%m-%d") if hasattr(latest, "strftime") else str(latest)
    return "未知"


def build_technical_snapshot_html(
    kline_result: KlineResult,
    bollinger_result: BollingerResult,
    fibonacci_result: FibonacciResult,
    price_action_result: PriceActionResult,
    data_quality: Optional[DataQuality] = None,
) -> str:
    klines = kline_result.klines
    date_text = _last_trade_date(klines, data_quality)
    if klines is None or klines.empty:
        return (
            '<div class="aistock-tech-snapshot">'
            '<div class="aistock-tech-head">'
            '<div class="aistock-tech-title">技术快照</div>'
            f'<div class="aistock-tech-date">最新交易日：{date_text}</div>'
            '</div>'
            '<div class="aistock-tech-sub">暂无可用行情数据</div>'
            '</div>'
        )

    latest = klines.iloc[-1]
    current = latest.get("close")
    previous = klines["close"].iloc[-2] if len(klines) >= 2 and "close" in klines.columns else None
    change = None
    change_pct = None
    try:
        if previous is not None and float(previous) != 0:
            change = float(current) - float(previous)
            change_pct = change / float(previous) * 100
    except (TypeError, ValueError):
        change = None
        change_pct = None

    trend_color = "#16a34a"
    try:
        if change is not None and float(change) < 0:
            trend_color = "#dc2626"
    except (TypeError, ValueError):
        pass

    high_20 = klines["high"].tail(20).max() if "high" in klines.columns else None
    low_20 = klines["low"].tail(20).min() if "low" in klines.columns else None
    volume = latest.get("volume") if "volume" in klines.columns else None
    pct_b = getattr(bollinger_result, "percent_b", None)
    fib_pos = getattr(fibonacci_result, "position_ratio", None)
    support = getattr(price_action_result, "support", None)
    resistance = getattr(price_action_result, "resistance", None)

    return (
        '<div class="aistock-tech-snapshot">'
        '<div class="aistock-tech-head">'
        '<div class="aistock-tech-title">技术快照</div>'
        f'<div class="aistock-tech-date">最新交易日：{date_text}</div>'
        '</div>'
        '<div class="aistock-tech-grid">'
        '<div class="aistock-tech-item aistock-tech-main">'
        '<div class="aistock-tech-label">当前股价</div>'
        f'<div class="aistock-tech-value">{_plain_number(current)}</div>'
        f'<div class="aistock-tech-sub" style="color:{trend_color};">{_signed_number(change)} / {_signed_number(change_pct, "%")}</div>'
        '</div>'
        '<div class="aistock-tech-item">'
        '<div class="aistock-tech-label">成交量</div>'
        f'<div class="aistock-tech-value">{_volume_text(volume)}</div>'
        '</div>'
        '<div class="aistock-tech-item">'
        '<div class="aistock-tech-label">20日区间</div>'
        f'<div class="aistock-tech-value">{_plain_number(low_20)} - {_plain_number(high_20)}</div>'
        '</div>'
        '<div class="aistock-tech-item">'
        '<div class="aistock-tech-label">支撑 / 压力</div>'
        f'<div class="aistock-tech-value">{_plain_number(support)} / {_plain_number(resistance)}</div>'
        '</div>'
        '<div class="aistock-tech-item">'
        '<div class="aistock-tech-label">布林位置</div>'
        f'<div class="aistock-tech-value">{_plain_number(pct_b, digits=2)}</div>'
        '</div>'
        '<div class="aistock-tech-item">'
        '<div class="aistock-tech-label">斐波位置</div>'
        f'<div class="aistock-tech-value">{_plain_number(float(fib_pos) * 100 if fib_pos is not None else None, "%", digits=1)}</div>'
        '</div>'
        '<div class="aistock-tech-item">'
        '<div class="aistock-tech-label">价格结构</div>'
        f'<div class="aistock-tech-value">{getattr(price_action_result, "trend", "") or "未知"}</div>'
        '</div>'
        '</div>'
        '</div>'
    )


def render_technical_snapshot(
    kline_result: KlineResult,
    bollinger_result: BollingerResult,
    fibonacci_result: FibonacciResult,
    price_action_result: PriceActionResult,
    data_quality: Optional[DataQuality] = None,
) -> None:
    st.markdown(
        build_technical_snapshot_html(
            kline_result,
            bollinger_result,
            fibonacci_result,
            price_action_result,
            data_quality,
        ),
        unsafe_allow_html=True,
    )


def _gauge_figure(score: float, color: str) -> go.Figure:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=float(score),
            number={"suffix": "", "font": {"size": 44, "color": "#0f172a"}},
            domain={"x": [0, 1], "y": [0, 1]},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#cbd5e1",
                         "tickfont": {"size": 10, "color": "#94a3b8"}},
                "bar": {"color": color, "thickness": 0.22},
                "bgcolor": "white",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 40], "color": "#fef2f2"},
                    {"range": [40, 60], "color": "#fffbeb"},
                    {"range": [60, 75], "color": "#eff6ff"},
                    {"range": [75, 100], "color": "#f0fdf4"},
                ],
                "threshold": {
                    "line": {"color": "#0f172a", "width": 3},
                    "thickness": 0.85,
                    "value": float(score),
                },
            },
        )
    )
    fig.update_layout(height=210, margin=dict(l=10, r=10, t=0, b=0))
    return fig


def render_score_hero(
    composite: CompositeResult,
    info: StockInfo,
    last_close: Optional[float],
    data_quality: Optional[DataQuality] = None,
) -> None:
    score = int(round(float(composite.score)))
    color = _score_color(score)
    action = composite.action
    name = info.name or info.code
    market_cn = {"a_share": "A股", "hk": "港股", "us": "美股"}.get(info.market.value, info.market.value)

    bg = {
        "#16a34a": "#ecfdf5",
        "#2563eb": "#eff6ff",
        "#f59e0b": "#fffbeb",
        "#dc2626": "#fef2f2",
    }.get(color, "#f1f5f9")

    breakdown = composite.breakdown or {}
    weights = composite.weights or {}
    conflicts = composite.conflicts or composite.signal_conflicts or []
    confidence = max(0.0, min(1.0, float(getattr(composite, "confidence", 1.0))))
    risk_level = getattr(composite, "risk_level", "中")
    summary = getattr(composite, "summary", "")
    conflict_html = (
        "".join(f"<li>{item}</li>" for item in conflicts)
        if conflicts
        else "<li>暂无明显冲突</li>"
    )
    if data_quality is None:
        quality_html = "<span>数据质量 <b>未提供</b></span>"
    else:
        latest = data_quality.latest_trade_date or "未知"
        quality_html = (
            f"<span>数据完整度 <b>{data_quality.completeness * 100:.0f}%</b></span>"
            f"<span>行情 <b>{data_quality.kline_days}</b> 日</span>"
            f"<span>最新交易日 <b>{latest}</b></span>"
            f"<span>缺失字段 <b>{len(data_quality.missing_fundamentals)}</b></span>"
        )

    st.markdown(
        f"""
        <div class="aistock-hero" style="--hero-bg:{bg};">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:16px;">
                <div style="flex:1; min-width:200px;">
                    <div class="aistock-hero-title">{name}</div>
                    <div class="aistock-hero-sub">{info.code} · {market_cn}
                    {(' · 最新价 <b style="color:#0f172a">' + f'{last_close:.2f}' + '</b>') if last_close else ''}</div>
                    <div style="margin-top:14px;">
                        <span class="aistock-action-badge" style="background:{color};">{action}</span>
                        <span style="display:inline-block; margin-left:8px; font-size:13px; color:#475569;">风险等级 <b style="color:#0f172a;">{risk_level}</b> · 置信度 <b style="color:#0f172a;">{confidence * 100:.0f}%</b></span>
                    </div>
                    <div style="margin-top:10px; font-size:13px; color:#475569; line-height:1.5;">{summary}</div>
                    <div style="margin-top:14px; display:flex; gap:18px; font-size:12px; color:#475569;">
                        <span>价值 <b>{int(round(breakdown.get('value', 0)))}</b> · 权重 {int(weights.get('value',0)*100)}%</span>
                        <span>布林带 <b>{int(round(breakdown.get('bollinger', 0)))}</b> · 权重 {int(weights.get('bollinger',0)*100)}%</span>
                        <span>斐波那契 <b>{int(round(breakdown.get('fibonacci', 0)))}</b> · 权重 {int(weights.get('fibonacci',0)*100)}%</span>
                        <span>Price Action <b>{int(round(breakdown.get('price_action', 0)))}</b> · 权重 {int(weights.get('price_action',0)*100)}%</span>
                    </div>
                    <div style="margin-top:12px; display:flex; flex-wrap:wrap; gap:12px; font-size:12px; color:#475569;">
                        {quality_html}
                    </div>
                    <div style="margin-top:12px; font-size:12px; color:#475569;">
                        <div style="font-weight:700; color:#0f172a; margin-bottom:4px;">冲突信号</div>
                        <ul style="margin:0; padding-left:18px; line-height:1.7;">{conflict_html}</ul>
                    </div>
                </div>
                <div style="width:240px;">
        """,
        unsafe_allow_html=True,
    )
    st.plotly_chart(_gauge_figure(score, color), use_container_width=True)
    st.markdown("</div></div></div>", unsafe_allow_html=True)


def _value_card_html(value_result: ValueResult, fundamentals: Fundamentals) -> str:
    score = int(round(float(value_result.score)))
    color = _score_color(score)
    accent = "#10b981"

    stats = _stat_grid([
        _stat_cell("PE (TTM)", _fmt(fundamentals.pe_ttm)),
        _stat_cell("PB", _fmt(fundamentals.pb)),
        _stat_cell("股息率", _fmt(fundamentals.dividend_yield, "%", digits=2)),
        _stat_cell("ROE", _fmt(fundamentals.roe, "%", digits=1)),
    ], cols=2)

    body = (
        f'<div class="aistock-card-body">'
        + stats
        + f'<div style="margin-top:12px;"><div class="aistock-section-label">估值评分</div>'
        + _progress_html(score, color)
        + f'<div style="font-size:11px; color:#64748b; margin-top:4px;">置信度 {float(getattr(value_result, "confidence", 1.0))*100:.0f}%</div>'
        + f'<div style="font-size:12px; color:#475569; margin-top:8px; line-height:1.45;">{getattr(value_result, "interpretation", "")}</div>'
        + f"</div>"
        + f'<div style="margin-top:auto; padding-top:12px;"><div class="aistock-section-label aistock-section-label-bold">信号</div>'
        + _signal_list(value_result.signals, accent)
        + "</div>"
        + "</div>"
    )

    return (
        f'<div class="aistock-card" style="--accent:{accent};">'
        f'<div class="aistock-card-head">'
        f'<div><div class="aistock-card-title">价值分析</div>'
        f'<div class="aistock-card-sub">{value_result.label}</div></div>'
        f'<div class="aistock-score-chip" style="background:{color};">{score}</div>'
        f'</div>'
        f'{body}'
        f'</div>'
    )


def _bollinger_card_html(result: BollingerResult) -> str:
    score = int(round(float(result.score)))
    color = _score_color(score)
    accent = "#0ea5e9"

    stats = _stat_grid([
        _stat_cell("上轨", _fmt(result.upper)),
        _stat_cell("下轨", _fmt(result.lower)),
        _stat_cell("中轨", _fmt(result.middle)),
        _stat_cell("带宽", _fmt(result.bandwidth, "", digits=3)),
    ], cols=2)

    pct_b = result.percent_b
    bw_pct = result.bandwidth_percentile

    if pct_b is not None:
        try:
            pct_b_val = max(0.0, min(1.0, float(pct_b)))
        except (TypeError, ValueError):
            pct_b_val = 0.5
    else:
        pct_b_val = 0.5

    cursor_pos = pct_b_val * 100.0
    pb_value_html = _fmt(pct_b, "", digits=2)
    bw_text = "数据不可用" if bw_pct is None else f"{float(bw_pct)*100:.0f}% 分位"

    track_html = (
        f'<div style="margin-top:12px;">'
        f'<div class="aistock-track-label"><span>超卖</span><span>中轨</span><span>超买</span></div>'
        f'<div class="aistock-track">'
        f'<div class="aistock-track-cursor" style="left:calc({cursor_pos:.1f}% - 2px);"></div>'
        f'</div>'
        f'<div style="font-size:11px; color:#64748b; margin-top:2px;">%B 位置：<b style="color:#0f172a;">{pb_value_html}</b> · 带宽 {bw_text}</div>'
        f'</div>'
    )

    body = (
        f'<div class="aistock-card-body">'
        + stats
        + track_html
        + f'<div style="font-size:11px; color:#64748b; margin-top:6px;">置信度 {float(getattr(result, "confidence", 1.0))*100:.0f}%</div>'
        + f'<div style="font-size:12px; color:#475569; margin-top:8px; line-height:1.45;">{getattr(result, "interpretation", "")}</div>'
        + f'<div style="margin-top:auto; padding-top:12px;"><div class="aistock-section-label aistock-section-label-bold">信号</div>'
        + _signal_list(result.signals, accent)
        + "</div>"
        + "</div>"
    )

    return (
        f'<div class="aistock-card" style="--accent:{accent};">'
        f'<div class="aistock-card-head">'
        f'<div><div class="aistock-card-title">布林带</div>'
        f'<div class="aistock-card-sub">{result.label}</div></div>'
        f'<div class="aistock-score-chip" style="background:{color};">{score}</div>'
        f'</div>'
        f'{body}'
        f'</div>'
    )


def _fibonacci_card_html(result: FibonacciResult) -> str:
    score = int(round(float(result.score)))
    color = _score_color(score)
    accent = "#8b5cf6"

    pos = result.position_ratio
    if pos is not None:
        try:
            pos_val = max(0.0, min(1.0, float(pos)))
        except (TypeError, ValueError):
            pos_val = 0.5
    else:
        pos_val = 0.5

    cursor_pos = pos_val * 100.0
    pos_text = "数据不可用" if pos is None else f"{float(pos)*100:.1f}% 回撤位"

    track_html = (
        f'<div style="margin-top:12px;">'
        f'<div class="aistock-track-label"><span>0% (低点)</span><span>50%</span><span>100% (高点)</span></div>'
        f'<div class="aistock-track">'
        f'<div class="aistock-track-zone" style="left:50%; width:11.8%;"></div>'
        f'<div class="aistock-track-cursor" style="left:calc({cursor_pos:.1f}% - 2px); background:#8b5cf6;"></div>'
        f'</div>'
        f'<div style="font-size:11px; color:#64748b; margin-top:2px;">当前位于：<b style="color:#8b5cf6;">{pos_text}</b>（紫框=50%-61.8% 观察区）</div>'
        f'</div>'
    )

    rows = ""
    for ratio, label in [(0.0, "0.0%"), (0.236, "23.6%"), (0.382, "38.2%"),
                          (0.5, "50.0%"), (0.618, "61.8%"), (0.786, "78.6%"), (1.0, "100.0%")]:
        price = (result.levels or {}).get(ratio)
        cls = ' class="aistock-fib-golden"' if 0.5 <= ratio <= 0.618 else ""
        rows += f'<div class="aistock-fib-row"><span{cls}>{label}</span><span>{_fmt(price)}</span></div>'

    levels_html = (
        f'<div style="margin-top:12px;">'
        f'<div class="aistock-section-label">关键回撤位（120日高低点）</div>'
        f'{rows}'
        f'</div>'
    )

    stats = _stat_grid([
        _stat_cell("最高点", _fmt(result.swing_high)),
        _stat_cell("最低点", _fmt(result.swing_low)),
    ], cols=2)

    body = (
        f'<div class="aistock-card-body">'
        + stats
        + track_html
        + levels_html
        + f'<div style="font-size:11px; color:#64748b; margin-top:6px;">置信度 {float(getattr(result, "confidence", 1.0))*100:.0f}%</div>'
        + f'<div style="font-size:12px; color:#475569; margin-top:8px; line-height:1.45;">{getattr(result, "interpretation", "")}</div>'
        + f'<div style="margin-top:auto; padding-top:12px;"><div class="aistock-section-label aistock-section-label-bold">信号</div>'
        + _signal_list(result.signals, accent)
        + "</div>"
        + "</div>"
    )

    return (
        f'<div class="aistock-card" style="--accent:{accent};">'
        f'<div class="aistock-card-head">'
        f'<div><div class="aistock-card-title">斐波那契</div>'
        f'<div class="aistock-card-sub">{result.label}</div></div>'
        f'<div class="aistock-score-chip" style="background:{color};">{score}</div>'
        f'</div>'
        f'{body}'
        f'</div>'
    )


def _price_action_card_html(result: PriceActionResult) -> str:
    score = int(round(float(result.score)))
    color = _score_color(score)
    accent = "#f97316"

    stats = _stat_grid([
        _stat_cell("当前价", _fmt(result.current_price)),
        _stat_cell("结构", result.trend or "未知"),
        _stat_cell("支撑", _fmt(result.support)),
        _stat_cell("压力", _fmt(result.resistance)),
    ], cols=2)

    pos = max(0.0, min(1.0, float(getattr(result, "range_position", 0.5))))
    cursor_pos = pos * 100.0
    volume_ratio = getattr(result, "volume_ratio", None)
    volume_text = "无量能数据" if volume_ratio is None else f"量比 {float(volume_ratio):.2f}"
    risks = getattr(result, "risks", []) or []
    signal_html = _signal_list(result.signals, accent)
    risk_html = _signal_list(risks, "#ef4444") if risks else _signal_list(["暂无明显价格行为风险"], "#cbd5e1")

    track_html = (
        f'<div style="margin-top:12px;">'
        f'<div class="aistock-track-label"><span>支撑</span><span>区间中部</span><span>压力</span></div>'
        f'<div class="aistock-track">'
        f'<div class="aistock-track-cursor" style="left:calc({cursor_pos:.1f}% - 2px); background:#f97316;"></div>'
        f'</div>'
        f'<div style="font-size:11px; color:#64748b; margin-top:2px;">状态：<b style="color:#0f172a;">{result.breakout_state}</b> · {volume_text}</div>'
        f'</div>'
    )

    body = (
        f'<div class="aistock-card-body">'
        + stats
        + track_html
        + f'<div style="font-size:11px; color:#64748b; margin-top:6px;">置信度 {float(getattr(result, "confidence", 1.0))*100:.0f}%</div>'
        + f'<div style="font-size:12px; color:#475569; margin-top:8px; line-height:1.45;">{getattr(result, "interpretation", "")}</div>'
        + f'<div style="margin-top:12px;"><div class="aistock-section-label aistock-section-label-bold">信号</div>{signal_html}</div>'
        + f'<div style="margin-top:auto; padding-top:12px;"><div class="aistock-section-label aistock-section-label-bold">风险</div>{risk_html}</div>'
        + "</div>"
    )

    return (
        f'<div class="aistock-card" style="--accent:{accent};">'
        f'<div class="aistock-card-head">'
        f'<div><div class="aistock-card-title">Price Action</div>'
        f'<div class="aistock-card-sub">{result.label}</div></div>'
        f'<div class="aistock-score-chip" style="background:{color};">{score}</div>'
        f'</div>'
        f'{body}'
        f'</div>'
    )


def render_analysis_grid(
    value_result: ValueResult,
    bollinger_result: BollingerResult,
    fibonacci_result: FibonacciResult,
    price_action_result: PriceActionResult,
    fundamentals: Fundamentals,
) -> None:
    html = (
        '<div class="aistock-cards-row">'
        + _value_card_html(value_result, fundamentals)
        + _bollinger_card_html(bollinger_result)
        + _fibonacci_card_html(fibonacci_result)
        + _price_action_card_html(price_action_result)
        + '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)
