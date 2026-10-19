"""Indicator research and simulated paper risk engine. No live brokerage code."""
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

@dataclass(frozen=True)
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

def ema(values: Sequence[float], period: int) -> list[float]:
    if period < 1 or not values:
        raise ValueError("period must be positive and values nonempty")
    alpha = 2 / (period + 1)
    out = [float(values[0])]
    for price in values[1:]:
        out.append(alpha * float(price) + (1 - alpha) * out[-1])
    return out

def vwap(candles: Sequence[Candle]) -> float:
    if not candles or any(c.volume < 0 for c in candles):
        raise ValueError("Provide candles with nonnegative volume")
    total = sum(c.volume for c in candles)
    if total <= 0:
        raise ValueError("VWAP requires positive cumulative volume")
    return sum(((c.high + c.low + c.close) / 3) * c.volume for c in candles) / total

def signal(candles: Sequence[Candle]) -> str:
    if len(candles) < 30:
        return "NO_SIGNAL"
    closes = [c.close for c in candles]
    nine, twentyone = ema(closes, 9), ema(closes, 21)
    price, weighted = closes[-1], vwap(candles)
    if price > weighted and price > nine[-1] > twentyone[-1] and nine[-1] > nine[-2]:
        return "BULLISH_WATCH"
    if price < weighted and price < nine[-1] < twentyone[-1] and nine[-1] < nine[-2]:
        return "BEARISH_WATCH"
    return "NO_SIGNAL"

@dataclass(frozen=True)
class SpreadRisk:
    width: float
    credit: float
    quantity: int
    max_profit: float
    max_loss: float

def credit_spread_risk(width: float, credit: float, quantity: int = 1) -> SpreadRisk:
    if width <= 0 or credit <= 0 or credit >= width or quantity < 1:
        raise ValueError("Require 0 < credit < spread width and positive quantity")
    multiplier = 100
    return SpreadRisk(width, credit, quantity, round(credit * quantity * multiplier, 2),
                      round((width - credit) * quantity * multiplier, 2))

class PaperPortfolio:
    """In-memory paper ledger. Does not route orders anywhere."""
    def __init__(self, starting_cash: float = 10000, max_risk_fraction: float = 0.02):
        if starting_cash <= 0 or not 0 < max_risk_fraction <= 1:
            raise ValueError("Invalid account/risk settings")
        self.starting_cash = float(starting_cash)
        self.available_risk = float(starting_cash) * max_risk_fraction
        self.ledger: list[dict] = []

    def open_paper_credit_spread(self, symbol: str, width: float, credit: float,
                                 quantity: int = 1) -> dict:
        if symbol not in {"SPY", "QQQ"}:
            raise ValueError("Only SPY/QQQ are supported")
        risk = credit_spread_risk(width, credit, quantity)
        if risk.max_loss > self.available_risk:
            raise ValueError("Paper risk limit exceeded")
        self.available_risk -= risk.max_loss
        record = {"mode": "PAPER_ONLY", "symbol": symbol,
                  "risk": risk.max_loss, "credit_received": risk.max_profit}
        self.ledger.append(record)
        return record
