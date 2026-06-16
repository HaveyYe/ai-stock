import unittest

from src.types import DataQuality, Fundamentals, StockInfo, Market
from src.analyzers.value_analyzer import ValueResult
from src.analyzers.bollinger_analyzer import BollingerResult
from src.analyzers.fibonacci_analyzer import FibonacciResult
from src.analyzers.price_action_analyzer import PriceActionResult
from src.scoring.composer import CompositeResult
from src.ui.report import build_report


def _make_info():
    return StockInfo(
        code="600519",
        symbol="600519",
        name="贵州茅台",
        market=Market.A_SHARE,
    )


def _make_fundamentals():
    return Fundamentals(pe_ttm=12, pb=2.0, roe=None)


def _make_value_result():
    return ValueResult(
        score=85,
        label="估值偏低",
        signals=["市盈率 12，处于低估区间", "市净率 2.0，处于低估区间"],
        details={},
    )


def _make_bollinger_result():
    return BollingerResult(
        score=50,
        upper=105.0,
        middle=100.0,
        lower=95.0,
        percent_b=0.45,
        bandwidth=0.1,
        bandwidth_percentile=0.35,
        label="中性区间",
        signals=["%B=0.45，处于布林带中轨附近，中性"],
    )


def _make_fibonacci_result():
    return FibonacciResult(
        score=85,
        levels={
            0.0: 110.0,
            0.236: 104.4,
            0.382: 100.76,
            0.5: 98.5,
            0.618: 96.24,
            0.786: 93.29,
            1.0: 87.0,
        },
        swing_high=110.0,
        swing_low=87.0,
        current_price=99.0,
        position_ratio=0.5217,
        label="黄金支撑区",
        signals=["价格处于斐波那契 50%-61.8% 黄金支撑区，看多"],
    )


def _make_price_action_result():
    return PriceActionResult(
        score=72,
        label="价格行为偏强",
        trend="上升结构",
        support=95.0,
        resistance=112.0,
        current_price=108.0,
        range_position=0.76,
        breakout_state="接近压力",
        body_ratio=0.55,
        volume_ratio=1.25,
        signals=["价格结构：上升结构"],
        risks=["价格接近近期压力区，追高性价比下降"],
        confidence=0.88,
        interpretation="趋势结构和短线行为偏积极。",
    )


def _make_composite_result():
    return CompositeResult(
        score=78,
        action="机会关注",
        action_en="Opportunity",
        breakdown={"value": 85, "bollinger": 50, "fibonacci": 85, "price_action": 72},
        weights={"value": 0.32, "bollinger": 0.23, "fibonacci": 0.2, "price_action": 0.25},
        confidence=0.82,
        risk_level="中",
        summary="多维评分偏积极，但仍需结合仓位和止损纪律。",
        conflicts=["基本面较好，但技术指标尚未形成共振"],
    )


def _make_data_quality():
    return DataQuality(
        completeness=0.62,
        kline_days=120,
        latest_trade_date="2026-06-12",
        missing_fundamentals=["ROE", "营收增长"],
        warnings=["缺少部分基本面字段"],
    )


class TestReport(unittest.TestCase):
    def setUp(self):
        self.report = build_report(
            _make_info(),
            _make_fundamentals(),
            _make_value_result(),
            _make_bollinger_result(),
            _make_fibonacci_result(),
            _make_price_action_result(),
            _make_composite_result(),
            _make_data_quality(),
        )

    def test_returns_non_empty_string(self):
        self.assertIsInstance(self.report, str)
        self.assertGreater(len(self.report), 0)

    def test_contains_stock_code_and_name(self):
        self.assertIn("600519", self.report)
        self.assertIn("贵州茅台", self.report)

    def test_contains_key_sections(self):
        self.assertIn("综合评分", self.report)
        self.assertIn("价值分析", self.report)
        self.assertIn("布林带", self.report)
        self.assertIn("斐波那契", self.report)
        self.assertIn("Price Action", self.report)
        self.assertIn("风险提示", self.report)

    def test_contains_action(self):
        self.assertIn("机会关注", self.report)

    def test_market_cn_mapping(self):
        self.assertIn("A股", self.report)

    def test_none_fundamentals_show_unavailable(self):
        self.assertIn("数据不可用", self.report)

    def test_non_none_fundamentals_appear(self):
        self.assertIn("12", self.report)
        self.assertIn("2.00", self.report)

    def test_section_order(self):
        idx_value = self.report.find("## 一、综合评分")
        idx_bollinger = self.report.find("## 三、技术形态 - 布林带")
        idx_fib = self.report.find("## 四、技术形态 - 斐波那契")
        idx_pa = self.report.find("## 五、Price Action")
        idx_risk = self.report.find("## 六、风险提示")
        self.assertLess(idx_value, idx_bollinger)
        self.assertLess(idx_bollinger, idx_fib)
        self.assertLess(idx_fib, idx_pa)
        self.assertLess(idx_pa, idx_risk)

    def test_fibonacci_levels_all_present(self):
        for label in ["0.0%", "23.6%", "38.2%", "50.0%", "61.8%", "78.6%", "100.0%"]:
            self.assertIn(label, self.report)

    def test_action_tip_present(self):
        self.assertIn("仍需确认趋势和控制仓位", self.report)

    def test_caution_action_tip(self):
        info = _make_info()
        fundamentals = _make_fundamentals()
        v = _make_value_result()
        b = _make_bollinger_result()
        f = _make_fibonacci_result()
        c = CompositeResult(
            score=25,
            action="风险回避",
            action_en="Avoid",
            breakdown={"value": 20, "bollinger": 25, "fibonacci": 30, "price_action": 22},
            weights={"value": 0.32, "bollinger": 0.23, "fibonacci": 0.2, "price_action": 0.25},
            confidence=0.9,
            risk_level="高",
            summary="风险信号占优或数据可信度不足，暂不适合激进参与。",
        )
        report = build_report(info, fundamentals, v, b, f, _make_price_action_result(), c)
        self.assertIn("风险信号占优，等待更好时机", report)

    def test_empty_signals_show_placeholder(self):
        v = ValueResult(score=50, label="估值合理", signals=[], details={})
        report = build_report(
            _make_info(),
            _make_fundamentals(),
            v,
            _make_bollinger_result(),
            _make_fibonacci_result(),
            _make_price_action_result(),
            _make_composite_result(),
        )
        self.assertIn("暂无", report)

    def test_contains_data_quality_and_conflicts(self):
        self.assertIn("数据质量", self.report)
        self.assertIn("完整度：62%", self.report)
        self.assertIn("缺失基本面字段：ROE、营收增长", self.report)
        self.assertIn("冲突信号", self.report)
        self.assertIn("技术指标尚未形成共振", self.report)

    def test_contains_confidence_and_risk(self):
        self.assertIn("置信度", self.report)
        self.assertIn("风险等级", self.report)

    def test_contains_price_action_details(self):
        self.assertIn("上升结构", self.report)
        self.assertIn("支撑 / 压力", self.report)
        self.assertIn("追高性价比下降", self.report)


if __name__ == "__main__":
    unittest.main()
