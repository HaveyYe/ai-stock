import unittest
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go

from src.analyzers.bollinger_analyzer import BollingerResult
from src.analyzers.fibonacci_analyzer import FibonacciResult
from src.types import KlineResult, Market, StockInfo
from src.ui.chart import render_chart


def make_klines(n=30):
    rows = []
    for i in range(n):
        p = 100 + i
        rows.append(
            {
                "date": datetime(2024, 1, 1) + timedelta(days=i),
                "open": p,
                "close": p + 1,
                "high": p + 2,
                "low": p - 1,
                "volume": 1000,
            }
        )
    return pd.DataFrame(rows)


def make_fixtures():
    info = StockInfo(
        code="600519", symbol="600519", name="贵州茅台", market=Market.A_SHARE
    )
    kl = KlineResult(info=info, klines=make_klines())
    b = BollingerResult(
        score=50,
        upper=110,
        middle=100,
        lower=90,
        percent_b=0.5,
        bandwidth=0.2,
        bandwidth_percentile=0.5,
        label="中性",
        signals=[],
    )
    f = FibonacciResult(
        score=85,
        levels={
            0.0: 90,
            0.236: 92.36,
            0.382: 93.82,
            0.5: 95,
            0.618: 96.18,
            0.786: 97.86,
            1.0: 100,
        },
        swing_high=100,
        swing_low=90,
        current_price=95,
        position_ratio=0.5,
        label="黄金支撑区",
        signals=[],
    )
    return info, kl, b, f


class TestRenderChart(unittest.TestCase):
    def test_returns_figure(self):
        _, kl, b, f = make_fixtures()
        fig = render_chart(kl, b, f)
        self.assertIsInstance(fig, go.Figure)

    def test_has_candlestick_and_bollinger_traces(self):
        _, kl, b, f = make_fixtures()
        fig = render_chart(kl, b, f)
        candle_count = sum(1 for tr in fig.data if isinstance(tr, go.Candlestick))
        scatter_count = sum(1 for tr in fig.data if isinstance(tr, go.Scatter))
        self.assertGreaterEqual(candle_count, 1)
        self.assertGreaterEqual(scatter_count, 3)
        self.assertGreaterEqual(len(fig.data), 4)

    def test_has_horizontal_lines(self):
        _, kl, b, f = make_fixtures()
        fig = render_chart(kl, b, f)
        self.assertGreaterEqual(len(fig.layout.shapes), 7)

    def test_title_contains_code(self):
        info, kl, b, f = make_fixtures()
        fig = render_chart(kl, b, f)
        title_obj = fig.layout.title
        title_text = title_obj.text if title_obj is not None else ""
        self.assertIn(info.code, title_text)

    def test_title_uses_name_when_present(self):
        info, kl, b, f = make_fixtures()
        fig = render_chart(kl, b, f)
        title_text = fig.layout.title.text
        self.assertIn(info.name, title_text)

    def test_title_fallback_when_name_empty(self):
        _, kl, b, f = make_fixtures()
        kl.info.name = ""
        fig = render_chart(kl, b, f)
        title_text = fig.layout.title.text
        self.assertIn(kl.info.code, title_text)
        self.assertNotIn(" ()", title_text)

    def test_subtitle_contains_market(self):
        info, kl, b, f = make_fixtures()
        fig = render_chart(kl, b, f)
        subtitle_text = fig.layout.title.subtitle.text or ""
        self.assertIn(info.market.value, subtitle_text)

    def test_rangebreaks_configured(self):
        _, kl, b, f = make_fixtures()
        fig = render_chart(kl, b, f)
        breaks = fig.layout.xaxis.rangebreaks
        self.assertIsNotNone(breaks)
        self.assertGreaterEqual(len(breaks), 1)


if __name__ == "__main__":
    unittest.main()
