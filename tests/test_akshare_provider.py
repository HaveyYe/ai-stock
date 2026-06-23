import importlib
import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import pandas as pd
import requests

from src.types import LatestSnapshot, Market, StockInfo, StockSearchResult


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

    def test_spch_direct_search_uses_static_chinese_alias_without_catalog(self):
        module = importlib.import_module("src.data.akshare_provider")
        provider = module.AkShareProvider()
        provider._catalog = lambda: self.fail("SPCH exact code should not load full catalog")

        results = provider.search_symbols("SPCH")

        self.assertEqual(results[0].code, "SPCH")
        self.assertIn("SPCX ETF", results[0].name)
        self.assertIn("2倍做多", results[0].name)

    def test_spcx_direct_search_does_not_resolve_to_spch(self):
        module = importlib.import_module("src.data.akshare_provider")
        provider = module.AkShareProvider()
        provider._catalog = lambda: self.fail("SPCX exact code should not load full catalog")

        results = provider.search_symbols("SPCX")

        self.assertEqual(results[0].code, "SPCX")
        self.assertIn("SpaceX", results[0].name)

    def test_spacex_alias_prefers_underlying_spcx_over_leveraged_etf(self):
        module = importlib.import_module("src.data.akshare_provider")
        provider = module.AkShareProvider()
        provider._catalog = lambda: self.fail("SpaceX static alias should not load full catalog")

        results = provider.search_symbols("SpaceX")

        self.assertEqual(results[0].code, "SPCX")

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
        intel = provider.search_symbols("INTEL")
        oracle = provider.search_symbols("ORACLE")

        self.assertEqual(apple[0].code, "AAPL")
        self.assertEqual(google[0].code, "GOOGL")
        self.assertEqual(intel[0].code, "INTC")
        self.assertEqual(oracle[0].code, "ORCL")

    def test_intel_chinese_alias_does_not_load_full_catalog(self):
        module = importlib.import_module("src.data.akshare_provider")
        provider = module.AkShareProvider()
        provider._catalog = lambda: self.fail("Intel alias should not load full catalog")

        results = provider.search_symbols("英特尔")

        self.assertEqual(results[0].code, "INTC")
        self.assertIn("Intel", results[0].name)

    def test_english_company_name_uses_yahoo_search_before_direct_code(self):
        module = importlib.import_module("src.data.akshare_provider")
        provider = module.AkShareProvider()
        provider._catalog = lambda: self.fail("English company search should not load full catalog")

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "quotes": [
                        {
                            "symbol": "SNOW",
                            "shortname": "Snowflake Inc.",
                            "quoteType": "EQUITY",
                        }
                    ]
                }

        with patch.object(provider._session, "get", return_value=FakeResponse()) as get:
            results = provider.search_symbols("SNOWFLAKE")

        self.assertEqual(results[0].code, "SNOW")
        self.assertEqual(results[0].name, "Snowflake Inc.")
        self.assertIn("finance/search", get.call_args.args[0])

    def test_yahoo_search_failure_falls_back_to_direct_code(self):
        module = importlib.import_module("src.data.akshare_provider")
        provider = module.AkShareProvider()
        provider._catalog = lambda: self.fail("direct fallback should not load full catalog")

        with patch.object(provider._session, "get", side_effect=requests.exceptions.ReadTimeout("slow")):
            results = provider.search_symbols("ABCDE")

        self.assertEqual(results[0].code, "ABCDE")
        self.assertEqual(results[0].market, Market.US)

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

    def test_us_code_without_snapshot_name_does_not_load_full_catalog(self):
        module = importlib.import_module("src.data.akshare_provider")
        provider = module.AkShareProvider()
        provider._fetch_snapshot = lambda market, symbol: module._TxSnapshot()
        provider._catalog = lambda: self.fail("US exact code fallback should not load full catalog")

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
            result = provider.get_klines("MBLY")

        self.assertEqual(result.info.code, "MBLY")
        self.assertEqual(result.info.name, "美股 MBLY")
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
            status_code = 200

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

    def test_yahoo_symbol_converts_dot_to_hyphen(self):
        module = importlib.import_module("src.data.akshare_provider")

        self.assertEqual(module._yahoo_symbol("BRK.A"), "BRK-A")
        self.assertEqual(module._yahoo_symbol("BRK.B"), "BRK-B")
        self.assertEqual(module._yahoo_symbol("AAPL"), "AAPL")

    def test_yahoo_404_is_treated_as_unknown_code(self):
        module = importlib.import_module("src.data.akshare_provider")
        provider = module.AkShareProvider()
        provider._fetch_snapshot = lambda market, symbol: module._TxSnapshot()

        captured_urls: list[str] = []

        class FakeNotFoundResponse:
            status_code = 404

            def raise_for_status(self):
                raise requests.HTTPError("404 Client Error: Not Found")

        def fake_get(url, **kwargs):
            captured_urls.append(url)
            return FakeNotFoundResponse()

        with patch.object(module.ak, "stock_us_daily", side_effect=IndexError("list index out of range")):
            with patch.object(provider._session, "get", side_effect=fake_get):
                with self.assertRaises(RuntimeError) as ctx:
                    provider.get_klines("SPACE")

        message = str(ctx.exception)
        self.assertIn("SPACE", message)
        self.assertNotIn("HTTPError", message)
        self.assertTrue(captured_urls)
        self.assertIn("/SPACE", captured_urls[0])

    def test_yahoo_request_uses_hyphenated_symbol_for_brk_a(self):
        module = importlib.import_module("src.data.akshare_provider")
        provider = module.AkShareProvider()
        provider._fetch_snapshot = lambda market, symbol: module._TxSnapshot(name="Berkshire")

        captured_urls: list[str] = []

        class FakeResponse:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "chart": {
                        "result": [
                            {
                                "timestamp": [1704067200],
                                "indicators": {
                                    "quote": [
                                        {
                                            "open": [400.0],
                                            "high": [410.0],
                                            "low": [395.0],
                                            "close": [405.0],
                                            "volume": [1000],
                                        }
                                    ]
                                },
                            }
                        ],
                        "error": None,
                    }
                }

        def fake_get(url, **kwargs):
            captured_urls.append(url)
            return FakeResponse()

        with patch.object(module.ak, "stock_us_daily", side_effect=requests.exceptions.SSLError("boom")):
            with patch.object(provider._session, "get", side_effect=fake_get):
                result = provider.get_klines("BRK.A")

        self.assertEqual(result.info.code, "BRK.A")
        self.assertTrue(captured_urls)
        self.assertIn("/BRK-A", captured_urls[0])

    def test_us_options_analysis_uses_yahoo_option_chain(self):
        module = importlib.import_module("src.data.akshare_provider")
        provider = module.AkShareProvider()
        info = StockInfo(code="AAPL", symbol="AAPL", name="Apple", market=Market.US)
        provider.get_latest_snapshot = lambda code: LatestSnapshot(info=info, last_price=100.0)

        class FakeResponse:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "optionChain": {
                        "result": [
                            {
                                "expirationDates": [1784246400],
                                "options": [
                                    {
                                        "expirationDate": 1784246400,
                                        "calls": [
                                            {
                                                "strike": 105,
                                                "volume": 300,
                                                "openInterest": 800,
                                                "impliedVolatility": 0.32,
                                            }
                                        ],
                                        "puts": [
                                            {
                                                "strike": 95,
                                                "volume": 100,
                                                "openInterest": 500,
                                                "impliedVolatility": 0.36,
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                        "error": None,
                    }
                }

        with patch.object(provider._session, "get", return_value=FakeResponse()) as get:
            result = provider.get_options_analysis("AAPL")

        self.assertTrue(result.available)
        self.assertEqual(result.support_strike, 95)
        self.assertEqual(result.resistance_strike, 105)
        self.assertIn("/AAPL", get.call_args.args[0])

    def test_us_options_analysis_retries_with_yahoo_crumb_on_401(self):
        module = importlib.import_module("src.data.akshare_provider")
        provider = module.AkShareProvider()
        info = StockInfo(code="AAPL", symbol="AAPL", name="Apple", market=Market.US)
        provider.get_latest_snapshot = lambda code: LatestSnapshot(info=info, last_price=100.0)
        captured = []

        class FakeResponse:
            def __init__(self, status_code=200, payload=None, text=""):
                self.status_code = status_code
                self._payload = payload or {}
                self.text = text

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise requests.HTTPError(f"{self.status_code} error")

            def json(self):
                return self._payload

        option_payload = {
            "optionChain": {
                "result": [
                    {
                        "expirationDates": [1784246400],
                        "options": [
                            {
                                "expirationDate": 1784246400,
                                "calls": [{"strike": 105, "volume": 300, "openInterest": 800}],
                                "puts": [{"strike": 95, "volume": 100, "openInterest": 500}],
                            }
                        ],
                    }
                ],
                "error": None,
            }
        }

        def fake_get(url, **kwargs):
            captured.append((url, kwargs.get("params")))
            if "query2.finance.yahoo.com/v7/finance/options" in url:
                return FakeResponse(401, text='{"finance":{"error":{"code":"Unauthorized"}}}')
            if "fc.yahoo.com" in url:
                return FakeResponse(404, text="")
            if "v1/test/getcrumb" in url:
                return FakeResponse(200, text="crumb-token")
            if "query1.finance.yahoo.com/v7/finance/options" in url:
                return FakeResponse(200, payload=option_payload)
            raise AssertionError(url)

        with patch.object(provider._session, "get", side_effect=fake_get):
            result = provider.get_options_analysis("AAPL")

        self.assertTrue(result.available)
        self.assertEqual(result.support_strike, 95)
        self.assertTrue(any(params and params.get("crumb") == "crumb-token" for _, params in captured))

    def test_non_us_options_analysis_degrades_without_error(self):
        module = importlib.import_module("src.data.akshare_provider")
        provider = module.AkShareProvider()

        result = provider.get_options_analysis("00700")

        self.assertFalse(result.available)
        self.assertIn("仅覆盖美股", result.warnings[0])


if __name__ == "__main__":
    unittest.main()
