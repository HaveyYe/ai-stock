import unittest
from datetime import datetime, timedelta

import pandas as pd

from src.analyzers.bollinger_analyzer import BollingerResult
from src.analyzers.fibonacci_analyzer import FibonacciResult
from src.analyzers.price_action_analyzer import PriceActionResult
from src.types import DataQuality, KlineResult, Market, OptionAnalysisResult, StockInfo
from src.ui.blocks import build_technical_snapshot_html


def _make_kline_result():
    rows = []
    for i in range(25):
        close = 100 + i
        rows.append(
            {
                "date": datetime(2026, 1, 1) + timedelta(days=i),
                "open": close - 1,
                "high": close + 2,
                "low": close - 3,
                "close": close,
                "volume": 20000 + i * 1000,
            }
        )
    info = StockInfo(code="600519", symbol="600519", name="贵州茅台", market=Market.A_SHARE)
    return KlineResult(info=info, klines=pd.DataFrame(rows))


class TestBlocks(unittest.TestCase):
    def test_technical_snapshot_contains_key_market_fields(self):
        html = build_technical_snapshot_html(
            _make_kline_result(),
            BollingerResult(
                score=55,
                upper=130,
                middle=120,
                lower=110,
                percent_b=0.75,
                bandwidth=0.1,
                bandwidth_percentile=0.5,
                label="中性",
                signals=[],
            ),
            FibonacciResult(
                score=60,
                levels={},
                swing_high=130,
                swing_low=95,
                current_price=124,
                position_ratio=0.6,
                label="中性",
                signals=[],
            ),
            PriceActionResult(
                score=58,
                label="结构偏积极",
                trend="偏强震荡",
                support=112,
                resistance=128,
                current_price=124,
                range_position=0.75,
                breakout_state="区间内",
            ),
            DataQuality(completeness=0.8, kline_days=25, latest_trade_date="2026-01-25"),
            OptionAnalysisResult(
                available=True,
                score=62,
                label="期权情绪偏积极",
                support_strike=115,
                resistance_strike=130,
            ),
        )

        self.assertIn("技术快照", html)
        self.assertIn("当前股价", html)
        self.assertIn("124.00", html)
        self.assertIn("+1.00", html)
        self.assertIn("+0.81%", html)
        self.assertIn("成交量", html)
        self.assertIn("综合支撑 / 压力", html)
        self.assertIn("正股技术位+Put密集区共振", html)
        self.assertIn("Put / Call 密集区", html)
        self.assertIn("115.00 / 130.00", html)
        self.assertIn("偏强震荡", html)
        self.assertIn("2026-01-25", html)


if __name__ == "__main__":
    unittest.main()
