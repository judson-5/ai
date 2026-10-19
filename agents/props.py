"""Research-only player prop evaluation using supplied historical results and prices."""
from dataclasses import dataclass
from math import sqrt
from statistics import mean, median
from typing import Sequence

@dataclass(frozen=True)
class PropReport:
    player: str
    market: str
    line: float
    side: str
    sample_size: int
    hit_rate: float
    average: float
    median: float
    modeled_probability: float
    implied_probability: float
    expected_value_per_unit: float
    probability_edge: float
    qualifies: bool

def evaluate_prop(player: str, market: str, line: float, side: str,
                  results: Sequence[float], decimal_odds: float,
                  min_samples: int = 10, min_edge: float = 0.05) -> PropReport:
    if side not in {"over", "under"}:
        raise ValueError("side must be 'over' or 'under'")
    if decimal_odds <= 1:
        raise ValueError("decimal_odds must be greater than 1")
    if not results or any(not isinstance(x, (int, float)) for x in results):
        raise ValueError("Supply numeric historical results")
    if min_samples < 1 or min_edge < 0:
        raise ValueError("Invalid screening thresholds")
    # A result equal to the line is a push, not a win.
    hits = sum(x > line if side == "over" else x < line for x in results)
    n = len(results)
    empirical = hits / n
    # Laplace smoothing prevents unjustified 0%/100% forecasts on small samples.
    p = (hits + 1) / (n + 2)
    fair = 1.0 / decimal_odds
    ev = p * (decimal_odds - 1) - (1 - p)
    edge = p - fair
    return PropReport(player, market, line, side, n, empirical, mean(results),
                      median(results), p, fair, ev, edge,
                      n >= min_samples and edge >= min_edge and ev > 0)
