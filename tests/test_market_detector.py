import unittest

from src.types import Market
from src.utils.market_detector import detect_market, normalize_symbol


class TestDetectMarket(unittest.TestCase):
    def test_a_share_600519(self):
        self.assertEqual(detect_market("600519"), Market.A_SHARE)

    def test_a_share_000001(self):
        self.assertEqual(detect_market("000001"), Market.A_SHARE)

    def test_a_share_300750(self):
        self.assertEqual(detect_market("300750"), Market.A_SHARE)

    def test_a_share_688981(self):
        self.assertEqual(detect_market("688981"), Market.A_SHARE)

    def test_a_share_strips_whitespace(self):
        self.assertEqual(detect_market("  600519 "), Market.A_SHARE)

    def test_a_share_lowercased_input(self):
        self.assertEqual(detect_market("600519"), Market.A_SHARE)

    def test_hk_5digits(self):
        self.assertEqual(detect_market("00700"), Market.HK)

    def test_hk_with_suffix(self):
        self.assertEqual(detect_market("0700.HK"), Market.HK)

    def test_hk_with_suffix_and_spaces(self):
        self.assertEqual(detect_market(" 0700.HK "), Market.HK)

    def test_us_letters(self):
        self.assertEqual(detect_market("AAPL"), Market.US)

    def test_us_with_suffix(self):
        self.assertEqual(detect_market("AAPL.US"), Market.US)

    def test_us_msft(self):
        self.assertEqual(detect_market("MSFT"), Market.US)

    def test_us_class_share_with_dot(self):
        self.assertEqual(detect_market("BRK.B"), Market.US)

    def test_invalid_code_raises(self):
        with self.assertRaises(ValueError):
            detect_market("INVALID")

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            detect_market("")

    def test_only_spaces_raises(self):
        with self.assertRaises(ValueError):
            detect_market("   ")


class TestNormalizeSymbol(unittest.TestCase):
    def test_a_share_symbol(self):
        self.assertEqual(normalize_symbol("600519", Market.A_SHARE), "600519")

    def test_a_share_symbol_stripped(self):
        self.assertEqual(normalize_symbol(" 600519 ", Market.A_SHARE), "600519")

    def test_hk_symbol_5digits(self):
        self.assertEqual(normalize_symbol("00700", Market.HK), "00700")

    def test_hk_symbol_with_suffix(self):
        self.assertEqual(normalize_symbol("0700.HK", Market.HK), "0700")

    def test_us_symbol(self):
        self.assertEqual(normalize_symbol("AAPL", Market.US), "AAPL")

    def test_us_symbol_with_suffix(self):
        self.assertEqual(normalize_symbol("AAPL.US", Market.US), "AAPL")

    def test_us_class_share_symbol(self):
        self.assertEqual(normalize_symbol("BRK.B", Market.US), "BRK.B")


if __name__ == "__main__":
    unittest.main()
