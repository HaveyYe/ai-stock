import plotly.graph_objects as go

from src import config
from src.analyzers.bollinger_analyzer import BollingerResult
from src.analyzers.fibonacci_analyzer import FibonacciResult
from src.types import KlineResult


def render_chart(
    kline_result: KlineResult,
    bollinger_result: BollingerResult,
    fibonacci_result: FibonacciResult,
) -> go.Figure:
    info = kline_result.info
    klines = kline_result.klines

    dates = klines["date"].tolist()

    fig = go.Figure()

    fig.add_trace(
        go.Candlestick(
            x=dates,
            open=klines["open"].tolist(),
            high=klines["high"].tolist(),
            low=klines["low"].tolist(),
            close=klines["close"].tolist(),
            increasing_line_color="red",
            decreasing_line_color="green",
            name="K线",
        )
    )

    close = klines["close"]
    window = config.BOLLINGER_WINDOW
    num_std = config.BOLLINGER_NUM_STD
    mid = close.rolling(window).mean()
    std = close.rolling(window).std(ddof=0)
    upper = mid + num_std * std
    lower = mid - num_std * std

    fig.add_trace(
        go.Scatter(
            x=dates,
            y=[float(v) for v in upper.tolist()],
            mode="lines",
            line=dict(color="#94a3b8", width=1, dash="dash"),
            name="布林上轨",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=[float(v) for v in mid.tolist()],
            mode="lines",
            line=dict(color="#2563eb", width=1.5),
            name="布林中轨",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=[float(v) for v in lower.tolist()],
            mode="lines",
            line=dict(color="#94a3b8", width=1, dash="dash"),
            name="布林下轨",
        )
    )

    for ratio, price in fibonacci_result.levels.items():
        fig.add_hline(
            y=float(price),
            line_dash="dot",
            line_color="#8b5cf6",
            opacity=0.4,
            annotation_text=f"{ratio * 100:.1f}%",
            annotation_position="right",
            annotation_font_size=9,
            annotation_font_color="#8b5cf6",
        )

    fig.add_hline(
        y=float(fibonacci_result.current_price),
        line_color="#f59e0b",
        line_width=2,
        annotation_text="当前价",
        annotation_position="left",
        annotation_font_size=10,
        annotation_font_color="#f59e0b",
    )

    title_text = (
        f"{info.name} ({info.code}) 技术分析图"
        if info.name
        else f"{info.code} 技术分析图"
    )

    market_cn = {"a_share": "A股", "hk": "港股", "us": "美股"}.get(
        info.market.value, info.market.value
    )

    fig.update_layout(
        title=dict(
            text=f"<b>{title_text}</b>",
            subtitle_text=f"市场: {info.market.value} · {market_cn}",
            font=dict(size=15, color="#0f172a"),
            subtitle_font=dict(size=11, color="#94a3b8"),
            x=0.01,
            xanchor="left",
        ),
        yaxis_title="价格",
        xaxis_rangeslider_visible=False,
        xaxis=dict(
            rangebreaks=[dict(bounds=["sat", "mon"])],
            gridcolor="#f1f5f9",
            linecolor="#e2e8f0",
        ),
        yaxis=dict(
            gridcolor="#f1f5f9",
            linecolor="#e2e8f0",
        ),
        height=560,
        template="plotly_white",
        font=dict(
            family="system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
            size=11,
            color="#475569",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(size=10, color="#64748b"),
            bgcolor="rgba(255,255,255,0)",
        ),
        margin=dict(l=8, r=8, t=60, b=20),
        hovermode="x unified",
        hoverlabel=dict(font_size=11, font_family="system-ui, sans-serif"),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
    )

    return fig
