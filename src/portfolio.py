from dataclasses import asdict, dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Iterable

from src.types import HoldingItem, Market, PortfolioItem, StockSearchResult


DEFAULT_PORTFOLIO_PATH = Path(".aistock") / "portfolio.json"


@dataclass
class PortfolioState:
    watchlist: list[PortfolioItem]
    holdings: list[HoldingItem]


def _now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _market_from_value(value) -> Market:
    if isinstance(value, Market):
        return value
    return Market(str(value))


def _portfolio_from_dict(row: dict) -> PortfolioItem:
    return PortfolioItem(
        code=str(row.get("code", "")).strip(),
        symbol=str(row.get("symbol", row.get("code", ""))).strip(),
        name=str(row.get("name", "")).strip(),
        market=_market_from_value(row.get("market")),
        added_at=row.get("added_at"),
    )


def _holding_from_dict(row: dict) -> HoldingItem:
    return HoldingItem(
        code=str(row.get("code", "")).strip(),
        symbol=str(row.get("symbol", row.get("code", ""))).strip(),
        name=str(row.get("name", "")).strip(),
        market=_market_from_value(row.get("market")),
        quantity=float(row.get("quantity", 0) or 0),
        cost_price=float(row.get("cost_price", 0) or 0),
        added_at=row.get("added_at"),
    )


def _item_to_dict(item) -> dict:
    data = asdict(item)
    market = data.get("market")
    if isinstance(market, Market):
        data["market"] = market.value
    return data


def load_portfolio(path: Path | str = DEFAULT_PORTFOLIO_PATH) -> PortfolioState:
    path = Path(path)
    if not path.exists():
        return PortfolioState(watchlist=[], holdings=[])
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return PortfolioState(watchlist=[], holdings=[])

    watchlist = []
    for row in payload.get("watchlist", []) if isinstance(payload, dict) else []:
        try:
            item = _portfolio_from_dict(row)
        except (TypeError, ValueError):
            continue
        if item.code:
            watchlist.append(item)

    holdings = []
    for row in payload.get("holdings", []) if isinstance(payload, dict) else []:
        try:
            item = _holding_from_dict(row)
        except (TypeError, ValueError):
            continue
        if item.code:
            holdings.append(item)

    return PortfolioState(watchlist=watchlist, holdings=holdings)


def save_portfolio(state: PortfolioState, path: Path | str = DEFAULT_PORTFOLIO_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "watchlist": [_item_to_dict(item) for item in state.watchlist],
        "holdings": [_item_to_dict(item) for item in state.holdings],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def portfolio_item_from_search(result: StockSearchResult) -> PortfolioItem:
    return PortfolioItem(
        code=result.code,
        symbol=result.symbol,
        name=result.name,
        market=result.market,
        added_at=_now_iso(),
    )


def holding_item_from_search(result: StockSearchResult, quantity: float, cost_price: float) -> HoldingItem:
    return HoldingItem(
        code=result.code,
        symbol=result.symbol,
        name=result.name,
        market=result.market,
        quantity=float(quantity),
        cost_price=float(cost_price),
        added_at=_now_iso(),
    )


def _replace_or_append(items: Iterable, new_item):
    output = []
    replaced = False
    for item in items:
        if item.market is new_item.market and item.symbol == new_item.symbol:
            output.append(new_item)
            replaced = True
        else:
            output.append(item)
    if not replaced:
        output.append(new_item)
    return output


def add_watchlist_item(item: PortfolioItem, path: Path | str = DEFAULT_PORTFOLIO_PATH) -> PortfolioState:
    state = load_portfolio(path)
    state.watchlist = _replace_or_append(state.watchlist, item)
    save_portfolio(state, path)
    return state


def remove_watchlist_item(code: str, path: Path | str = DEFAULT_PORTFOLIO_PATH) -> PortfolioState:
    state = load_portfolio(path)
    target = code.upper()
    state.watchlist = [item for item in state.watchlist if item.code.upper() != target]
    save_portfolio(state, path)
    return state


def upsert_holding_item(item: HoldingItem, path: Path | str = DEFAULT_PORTFOLIO_PATH) -> PortfolioState:
    state = load_portfolio(path)
    state.holdings = _replace_or_append(state.holdings, item)
    save_portfolio(state, path)
    return state


def remove_holding_item(code: str, path: Path | str = DEFAULT_PORTFOLIO_PATH) -> PortfolioState:
    state = load_portfolio(path)
    target = code.upper()
    state.holdings = [item for item in state.holdings if item.code.upper() != target]
    save_portfolio(state, path)
    return state
