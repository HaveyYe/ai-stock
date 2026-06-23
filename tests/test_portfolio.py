import tempfile
from pathlib import Path
import unittest

from src.portfolio import (
    add_watchlist_item,
    holding_item_from_search,
    import_portfolio_file,
    load_portfolio,
    portfolio_item_from_search,
    portfolio_path_for_user,
    remove_holding_item,
    remove_watchlist_item,
    save_portfolio,
    upsert_holding_item,
    PortfolioState,
)
from src.types import HoldingItem, Market, PortfolioItem, StockSearchResult


class TestPortfolioStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "portfolio.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_missing_file_returns_empty_state(self):
        state = load_portfolio(self.path)

        self.assertEqual(state.watchlist, [])
        self.assertEqual(state.holdings, [])

    def test_load_bad_json_returns_empty_state(self):
        self.path.write_text("{bad", encoding="utf-8")

        state = load_portfolio(self.path)

        self.assertEqual(state.watchlist, [])
        self.assertEqual(state.holdings, [])

    def test_save_and_load_round_trip(self):
        state = PortfolioState(
            watchlist=[
                PortfolioItem(
                    code="AAPL",
                    symbol="AAPL",
                    name="Apple",
                    market=Market.US,
                )
            ],
            holdings=[
                HoldingItem(
                    code="00700",
                    symbol="00700",
                    name="腾讯",
                    market=Market.HK,
                    quantity=100,
                    cost_price=300,
                )
            ],
        )

        save_portfolio(state, self.path)
        loaded = load_portfolio(self.path)

        self.assertEqual(loaded.watchlist[0].code, "AAPL")
        self.assertEqual(loaded.watchlist[0].market, Market.US)
        self.assertEqual(loaded.holdings[0].quantity, 100)

    def test_add_and_remove_watchlist_item(self):
        item = PortfolioItem(code="AAPL", symbol="AAPL", name="Apple", market=Market.US)

        add_watchlist_item(item, self.path)
        state = remove_watchlist_item("aapl", self.path)

        self.assertEqual(state.watchlist, [])

    def test_upsert_and_remove_holding_item(self):
        item = HoldingItem(
            code="AAPL",
            symbol="AAPL",
            name="Apple",
            market=Market.US,
            quantity=2,
            cost_price=100,
        )
        updated = HoldingItem(
            code="AAPL",
            symbol="AAPL",
            name="Apple",
            market=Market.US,
            quantity=3,
            cost_price=120,
        )

        upsert_holding_item(item, self.path)
        state = upsert_holding_item(updated, self.path)
        self.assertEqual(len(state.holdings), 1)
        self.assertEqual(state.holdings[0].quantity, 3)

        state = remove_holding_item("AAPL", self.path)
        self.assertEqual(state.holdings, [])

    def test_build_items_from_search_result(self):
        result = StockSearchResult(
            code="AAPL",
            symbol="AAPL",
            name="Apple",
            market=Market.US,
        )

        watch = portfolio_item_from_search(result)
        holding = holding_item_from_search(result, 5, 150)

        self.assertEqual(watch.code, "AAPL")
        self.assertEqual(holding.quantity, 5)
        self.assertEqual(holding.cost_price, 150)

    def test_portfolio_path_is_scoped_by_username(self):
        alice = portfolio_path_for_user("Alice")
        bob = portfolio_path_for_user("bob")

        self.assertNotEqual(alice, bob)
        self.assertEqual(alice.name, "alice.json")
        self.assertEqual(bob.name, "bob.json")

    def test_import_portfolio_file_merges_legacy_data(self):
        source = Path(self.tmp.name) / "legacy.json"
        target = Path(self.tmp.name) / "admin.json"
        save_portfolio(
            PortfolioState(
                watchlist=[PortfolioItem(code="AAPL", symbol="AAPL", name="Apple", market=Market.US)],
                holdings=[],
            ),
            source,
        )
        save_portfolio(
            PortfolioState(
                watchlist=[PortfolioItem(code="MSFT", symbol="MSFT", name="Microsoft", market=Market.US)],
                holdings=[HoldingItem(code="AAPL", symbol="AAPL", name="Apple", market=Market.US, quantity=2, cost_price=100)],
            ),
            target,
        )

        merged = import_portfolio_file(source, target)

        self.assertEqual([item.code for item in merged.watchlist], ["MSFT", "AAPL"])
        loaded = load_portfolio(target)
        self.assertEqual(len(loaded.watchlist), 2)
        self.assertEqual(loaded.holdings[0].code, "AAPL")


if __name__ == "__main__":
    unittest.main()
