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

    def test_common_alias_search_does_not_load_full_catalog(self):
        module = importlib.import_module("src.data.akshare_provider")
        provider = module.AkShareProvider()
        provider._catalog = lambda: self.fail("common aliases should not load full catalog")

        results = provider.search_symbols("苹果")

        self.assertEqual(results[0].code, "AAPL")

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


if __name__ == "__main__":
    unittest.main()
