"""Validated market records shared by replay and Alpaca's read-only adapter."""
from dataclasses import dataclass
from datetime import datetime
import re
from research_common.validation import number, stamp


@dataclass(frozen=True)
class Bar:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self):
        if (self.symbol not in {"SPY", "QQQ"} or self.timestamp.tzinfo is None
                or self.timestamp.second != 0 or self.timestamp.microsecond != 0):
            raise ValueError("SPY/QQQ timezone-aware minute-aligned bars required")
        for value in (self.open, self.high, self.low, self.close):
            number(value, minimum=.00001)
        number(self.volume, minimum=0)
        if not self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high:
            raise ValueError("Invalid OHLC geometry")

    @classmethod
    def parse(cls, symbol, row):
        if symbol not in {"SPY", "QQQ"}:
            raise ValueError("Only SPY/QQQ are supported")
        o, h, l, c = [number(row[k], minimum=.00001) for k in ("o", "h", "l", "c")]
        if not l <= min(o, c) <= max(o, c) <= h:
            raise ValueError("Invalid OHLC geometry")
        return cls(symbol, stamp(row["t"]), o, h, l, c, number(row["v"], minimum=0))


@dataclass(frozen=True)
class Option:
    contract: str
    underlying: str
    expiry: datetime
    kind: str
    strike: float
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    delta: float
    timestamp: datetime

    def __post_init__(self):
        from zoneinfo import ZoneInfo
        match = re.fullmatch(r"(SPY|QQQ)(\d{6})([CP])(\d{8})", self.contract)
        if not match or self.expiry.tzinfo is None or self.timestamp.tzinfo is None:
            raise ValueError("Supported OCC contract and aware timestamps required")
        root, date, kind, strike = match.groups()
        expected = datetime.strptime(date, "%y%m%d").replace(hour=16, tzinfo=ZoneInfo("America/New_York"))
        if (self.underlying != root or self.kind != kind or self.strike != int(strike)/1000
                or self.expiry != expected):
            raise ValueError("Option metadata must match OCC contract")
        number(self.bid, minimum=0)
        number(self.ask, minimum=.00001)
        number(self.delta, minimum=-1, maximum=1)
        if self.ask < self.bid or (kind == "C" and self.delta < 0) or (kind == "P" and self.delta > 0):
            raise ValueError("Invalid option quote or delta")
        if any(type(size) is not int or size < 0 for size in (self.bid_size, self.ask_size)):
            raise ValueError("Quote sizes must be nonnegative integers")

    @classmethod
    def parse(cls, contract, snapshot):
        from datetime import timezone
        match = re.fullmatch(r"(SPY|QQQ)(\d{6})([CP])(\d{8})", contract)
        if not match:
            raise ValueError("Unsupported OCC option contract")
        root, expiry, kind, strike = match.groups()
        # Expiration close is used only as a conservative time cutoff, not settlement.
        from zoneinfo import ZoneInfo
        expires = datetime.strptime(expiry, "%y%m%d").replace(hour=16, tzinfo=ZoneInfo("America/New_York"))
        q, greeks = snapshot["latestQuote"], snapshot["greeks"]
        bid, ask = number(q["bp"], minimum=0), number(q["ap"], minimum=.00001)
        if ask < bid:
            raise ValueError("Crossed option quote")
        bs, az = number(q["bs"], minimum=0), number(q["as"], minimum=0)
        if not bs.is_integer() or not az.is_integer():
            raise ValueError("Quote sizes must be integer contracts")
        delta = number(greeks["delta"], minimum=-1, maximum=1)
        if (kind == "C" and delta < 0) or (kind == "P" and delta > 0):
            raise ValueError("Option delta sign mismatch")
        return cls(contract, root, expires.astimezone(timezone.utc), kind,
                   int(strike)/1000, bid, ask, int(bs), int(az), delta, stamp(q["t"]))


def ordered_bars(bars):
    if len({b.symbol for b in bars}) > 1:
        raise ValueError("Mixed underlying series")
    if any(a.timestamp >= b.timestamp for a, b in zip(bars, bars[1:])):
        raise ValueError("Bars must be unique and strictly chronological")
