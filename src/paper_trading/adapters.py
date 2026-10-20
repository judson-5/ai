"""Alpaca market data only: no trading host, account endpoint or order method."""
from research_common.http import JsonGet, secret, DataUnavailable
from .market import Bar, Option, ordered_bars


class AlpacaData:
    def __init__(self, transport=None, stock_feed="iex", option_feed="indicative"):
        if stock_feed not in {"iex", "sip"} or option_feed not in {"indicative", "opra"}:
            raise ValueError("Unsupported Alpaca feed")
        self.stock_feed, self.option_feed = stock_feed, option_feed
        self.transport = transport or JsonGet("https://data.alpaca.markets", {
            "APCA-API-KEY-ID": secret("ALPACA_API_KEY"),
            "APCA-API-SECRET-KEY": secret("ALPACA_SECRET_KEY")})

    def _pages(self, path, params, field):
        seen = set()
        for _ in range(100):
            page = self.transport.get(path, params)
            if field not in page or not isinstance(page[field], dict):
                raise DataUnavailable("Malformed provider page")
            yield page[field]
            token = page.get("next_page_token")
            if not token:
                return
            if token in seen:
                raise DataUnavailable("Repeated provider page token")
            seen.add(token)
            params = {**params, "page_token": token}
        raise DataUnavailable("Provider pagination limit reached; refusing truncated data")

    def bars(self, symbol, start, end):
        if symbol not in {"SPY", "QQQ"}:
            raise ValueError("Only SPY/QQQ")
        rows = []
        for page in self._pages("/v2/stocks/bars", {
            "symbols": symbol, "timeframe": "1Min", "start": start.isoformat(),
            "end": end.isoformat(), "adjustment": "raw", "feed": self.stock_feed,
            "sort": "asc", "limit": 10000}, "bars"):
            rows.extend(Bar.parse(symbol, row) for row in page.get(symbol, []))
        ordered_bars(rows)
        return rows

    def options(self, symbol):
        if symbol not in {"SPY", "QQQ"}:
            raise ValueError("Only SPY/QQQ")
        rows, seen = [], set()
        for page in self._pages(f"/v1beta1/options/snapshots/{symbol}",
                                {"feed": self.option_feed, "limit": 1000}, "snapshots"):
            for contract, snapshot in page.items():
                if contract in seen:
                    raise DataUnavailable("Duplicate option contract across provider pages")
                seen.add(contract)
                try:
                    rows.append(Option.parse(contract, snapshot))
                except (ValueError, KeyError, TypeError):
                    # Missing greeks or quotes make this contract ineligible.
                    continue
        return rows
