import importlib
import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import pandas as pd
import requests

from src.types import Market, StockSearchResult


class TestAkShareProviderSideEffects(unittest.TestCase):
    def test_import_does_not_mutate_proxy_env_or_patch_requests(self):
        key = "AISTOCK_TEST_PROXY"
        os.environ[key] = "http://127.0.0.1:9999"
        original_session_init = requests.Session.__init__

        try:
            module = importlib.import_module("src.data.akshare_provider")
            importlib.reload(module)

            self.assertEqual(os.environ[key], "http://127.0.0.1:9999")
            self.assertIs(requests.Session.__init__, original_session_init)
        finally:
            os.environ.pop(key, None)

    def test_disable_proxy_is_scoped_to_provider_session(self):
        module = importlib.import_module("src.data.akshare_provider")
        provider = module.AkShareProvider(disable_proxy=True)

        self.assertFalse(provider._session.trust_env)
        self.assertEqual(provider._session.proxies, {"http": "", "https": ""})

    def test_valid_code_search_does_not_load_catalog(self):
        module = importlib.import_module("src.data.akshare_provider")
        provider = module.AkShareProvider()
        provider._catalog = lambda: self.fail("exact code should not load catalog")

        results = provider.search_symbols("NOk")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].code, "NOK")
        self.assertEqual(results[0].market, Market.US)

    def test_name_search_uses_cached_catalog(self):
        module = importlib.import_module("src.data.akshare_provider")
        provider = module.AkShareProvider()
        provider._search_cache = [
            StockSearchResult(
                code="NOK",
                symbol="NOK",
                name="诺基亚 Nokia",
                market=Market.US,
            )
        ]

        results = provider.search_symbols("诺基亚")

        self.assertEqual(results[0].code, "NOK")

    def test_a_share_code_search_uses_catalog_name_when_available(self):
        module = importlib.import_module("src.data.akshare_provider")
        provider = module.AkShareProvider()
        provider._search_cache = [
            StockSearchResult(
                code="300351",
                symbol="300351",
                name="永贵电器",
                market=Market.A_SHARE,
            )
        ]

        results = provider.search_symbols("300351")

        self.assertEqual(results[0].code, "300351")
        self.assertEqual(results[0].name, "永贵电器")
        self.assertEqual(results[0].market, Market.A_SHARE)

    def test_a_share_code_search_only_loads_a_share_catalog_for_name(self):
        module = importlib.import_module("src.data.akshare_provider")
        provider = module.AkShareProvider()
        provider._load_a_share_catalog = lambda: [
            StockSearchResult(
                code="300351",
                symbol="300351",
                name="永贵电器",
                market=Market.A_SHARE,
            )
        ]
        provider._load_hk_catalog = lambda: self.fail("A-share direct search should not load HK catalog")
        provider._load_us_catalog = lambda: self.fail("A-share direct search should not load US catalog")

        results = provider.search_symbols("300351")

        self.assertEqual(results[0].name, "永贵电器")

    def test_common_alias_search_does_not_load_full_catalog(self):
        module = importlib.import_module("src.data.akshare_provider")
        provider = module.AkShareProvider()
        provider._catalog = lambda: self.fail("common aliases should not load full catalog")

        results = provider.search_symbols("苹果")

        self.assertEqual(results[0].code, "AAPL")

    def test_company_name_that_looks_like_us_symbol_prefers_alias(self):
        module = importlib.import_module("src.data.akshare_provider")
        provider = module.AkShareProvider()
        provider._catalog = lambda: self.fail("common aliases should not load full catalog")

        apple = provider.search_symbols("APPLE")
        google = provider.search_symbols("GOOGLE")

        self.assertEqual(apple[0].code, "AAPL")
        self.assertEqual(google[0].code, "GOOGL")

    def test_get_klines_continues_when_snapshot_name_missing(self):
        module = importlib.import_module("src.data.akshare_provider")
        provider = module.AkShareProvider()
        provider._fetch_snapshot = lambda market, symbol: module._TxSnapshot()

        rows = []
        for i in range(25):
            rows.append(
                {
                    "date": datetime(2024, 1, 1) + timedelta(days=i),
                    "open": 10 + i,
                    "high": 11 + i,
                    "low": 9 + i,
                    "close": 10.5 + i,
                    "volume": 1000,
                }
            )

        with patch.object(module.ak, "stock_us_daily", return_value=pd.DataFrame(rows)):
            result = provider.get_klines("NOk")

        self.assertEqual(result.info.code, "NOK")
        self.assertIn("Nokia", result.info.name)
        self.assertFalse(result.klines.empty)

    def test_a_share_klines_falls_back_to_eastmoney_when_sina_ssl_fails(self):
        module = importlib.import_module("src.data.akshare_provider")
        provider = module.AkShareProvider()
        provider._fetch_snapshot = lambda market, symbol: module._TxSnapshot(name="永贵电器")
        rows = pd.DataFrame(
            [
                {
                    "日期": "2026-06-12",
                    "开盘": 20.0,
                    "最高": 21.0,
                    "最低": 19.5,
                    "收盘": 20.8,
                    "成交量": 100000,
                },
                {
                    "日期": "2026-06-15",
                    "开盘": 20.8,
                    "最高": 22.0,
                    "最低": 20.2,
                    "收盘": 21.6,
                    "成交量": 120000,
                },
            ]
        )

        with patch.object(module.ak, "stock_zh_a_daily", side_effect=requests.exceptions.SSLError("boom")):
            with patch.object(module.ak, "stock_zh_a_hist", return_value=rows) as fallback:
                result = provider.get_klines("300351")

        fallback.assert_called_once()
        self.assertEqual(result.info.code, "300351")
        self.assertEqual(result.info.name, "永贵电器")
        self.assertEqual(len(result.klines), 2)
        self.assertEqual(float(result.klines["close"].iloc[-1]), 21.6)

    def test_us_klines_falls_back_to_yahoo_when_akshare_ssl_fails(self):
        module = importlib.import_module("src.data.akshare_provider")
        provider = module.AkShareProvider()
        provider._fetch_snapshot = lambda market, symbol: module._TxSnapshot(name="Mobileye")

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "chart": {
                        "result": [
                            {
                                "timestamp": [1704067200, 1704153600],
                                "indicators": {
                                    "quote": [
                                        {
                                            "open": [40.0, 41.0],
                                            "high": [42.0, 43.0],
                                            "low": [39.0, 40.0],
                                            "close": [41.0, 42.0],
                                            "volume": [1000, 1200],
                                        }
                                    ]
                                },
                            }
                        ],
                        "error": None,
                    }
                }

        with patch.object(module.ak, "stock_us_daily", side_effect=requests.exceptions.SSLError("boom")):
            with patch.object(provider._session, "get", return_value=FakeResponse()):
                result = provider.get_klines("MBLY")

        self.assertEqual(result.info.code, "MBLY")
        self.assertEqual(result.info.name, "Mobileye")
        self.assertEqual(len(result.klines), 2)
        self.assertEqual(float(result.klines["close"].iloc[-1]), 42.0)


if __name__ == "__main__":
    unittest.main()
