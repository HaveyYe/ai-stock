import re

from src.types import Market


def _normalize(code: str) -> str:
    return code.strip().upper()


def detect_market(code: str) -> Market:
    if not code or not code.strip():
        raise ValueError(f"无法识别的股票代码: {code!r}")

    c = _normalize(code)

    if c.endswith(".US"):
        pure = c[:-3].strip()
        if re.fullmatch(r"[A-Z]{1,6}", pure):
            return Market.US

    if c.endswith(".HK"):
        pure = c[:-3].strip()
        if re.fullmatch(r"\d{1,5}", pure):
            return Market.HK

    if re.fullmatch(r"\d{6}", c):
        prefix2 = c[:2]
        if prefix2 in {"60", "68", "30", "00"}:
            return Market.A_SHARE

    if re.fullmatch(r"\d{5}", c):
        return Market.HK

    if re.fullmatch(r"[A-Z]{1,6}", c):
        return Market.US

    raise ValueError(f"无法识别的股票代码: {code!r}")


def normalize_symbol(code: str, market: Market) -> str:
    c = _normalize(code)

    if market is Market.A_SHARE:
        digits = re.sub(r"\D", "", c)
        if not re.fullmatch(r"\d{6}", digits):
            raise ValueError(f"无效的 A 股代码: {code!r}")
        return digits

    if market is Market.HK:
        if c.endswith(".HK"):
            digits = c[:-3].strip()
        else:
            digits = c
        digits = re.sub(r"\D", "", digits)
        if not digits:
            raise ValueError(f"无效的港股代码: {code!r}")
        return digits

    if market is Market.US:
        if c.endswith(".US"):
            pure = c[:-3].strip()
        else:
            pure = c
        if not re.fullmatch(r"[A-Z]{1,6}", pure):
            raise ValueError(f"无效的美股代码: {code!r}")
        return pure

    raise ValueError(f"不支持的市场类型: {market!r}")
