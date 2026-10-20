"""Deliberately conservative historical model; no fitted calibration claims."""
from math import sqrt
from statistics import mean, median


def wilson_lower(hits, count, z=1.645):
    """One-sided 95% Wilson lower bound (sampling uncertainty only)."""
    p = hits / count
    return (p + z*z/(2*count) - z*sqrt(p*(1-p)/count + z*z/(4*count*count))) / (1+z*z/count)


def estimate(logs, line, side, projected_opportunities, matchup_factor, market_probability):
    recent = logs[-30:]
    # Do not increase the projection beyond past opportunity or matchup performance.
    ratio = min(1.0, projected_opportunities / mean(x["opportunities"] for x in recent))
    factor = min(1.0, matchup_factor)
    outcomes = [x["value"] * ratio * factor for x in recent]
    hits = sum(x > line if side == "over" else x < line for x in outcomes)
    # Include unadjusted history too: a lower opportunity projection must not
    # spuriously increase confidence in an under without model validation.
    raw_hits = sum(x["value"] > line if side == "over" else x["value"] < line for x in recent)
    lower = min(wilson_lower(hits, len(recent)), wilson_lower(raw_hits, len(recent)))
    # Shrink toward the weaker market estimate without treating the market as
    # a hard ceiling (which would make positive reference EV impossible).
    probability = min(lower, .75*lower + .25*market_probability)
    return {"sample_size": len(recent), "recent_mean": mean(x["value"] for x in recent),
            "recent_median": median(x["value"] for x in recent),
            "last_5_mean": mean(x["value"] for x in recent[-5:]),
            "historical_lower_bound": lower, "market_probability": market_probability,
            "modeled_probability": probability, "opportunity_ratio": ratio,
            "matchup_factor_used": factor,
            "model": "wilson_95_lower_market_shrinkage_v1"}
