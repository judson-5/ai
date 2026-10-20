"""Fail-closed orchestration with an audit record for every candidate."""
from statistics import mean
from research_common.validation import number, stamp, fresh, evidence, utcnow
from .adapters import BOOK_OWNERS, SPORTS, MARKETS
from .model import estimate


def research(candidate, now=None):
    now = now or utcnow()
    result = {"id": candidate.get("id") if isinstance(candidate, dict) else None,
              "recommended": False, "reasons": []}
    try:
        if not isinstance(candidate, dict):
            raise ValueError("Candidate must be an object")
        for key in ("id", "event_id", "player_id", "player", "market", "period"):
            if not isinstance(candidate[key], str) or not candidate[key].strip():
                raise ValueError("Missing identity or market")
        if candidate["sport"] not in SPORTS or candidate["side"] not in {"over", "under"}:
            raise ValueError("Unsupported sport or side")
        if candidate["period"] != "full_game":
            raise ValueError("Only explicitly mapped full_game markets supported")
        if candidate["market"] not in MARKETS[candidate["sport"]]:
            raise ValueError("Unsupported full-game market mapping")
        if candidate["promotional"] is not False or candidate["boosted"] is not False:
            raise ValueError("Promotional/boosted or unknown line types excluded")
        evidence(candidate, now, 600)
        if stamp(candidate["event_start"]) <= now:
            raise ValueError("Pregame lines only")
        line = number(candidate["line"], minimum=0)
        # Integer lines require provider-specific push/void payouts. Never invent them.
        if line.is_integer():
            raise ValueError("Integer lines unsupported without push/void settlement model")
        context = evidence(candidate["context"], now)
        if context["injury_status"] != "available" or context["lineup_status"] != "confirmed":
            raise ValueError("Injury or lineup uncertainty")
        opportunities = number(context["projected_opportunities"], minimum=0.00001)
        matchup = number(context["matchup_factor"], minimum=0.5, maximum=1.5)
        if not context["opportunity_unit"] or not context["matchup_notes"]:
            raise ValueError("Opportunity units and matchup evidence required")
        logs = candidate["game_logs"]
        if not isinstance(logs, list) or len(logs) < 20:
            raise ValueError("At least 20 historical games required")
        seen, checked = set(), []
        for log in logs:
            when = stamp(log["timestamp"])
            if when >= now or when >= stamp(candidate["event_start"]) or log["game_id"] in seen:
                raise ValueError("Duplicate or future history")
            if not log["source"].startswith("https://"):
                raise ValueError("Historical provenance required")
            seen.add(log["game_id"])
            checked.append({"timestamp": when, "value": number(log["value"], minimum=0),
                            "opportunities": number(log["opportunities"], minimum=0.00001)})
        checked.sort(key=lambda x: x["timestamp"])
        if (now - checked[-1]["timestamp"]).days > 45:
            raise ValueError("Recent statistics unavailable")
        owners, comparisons = set(), []
        for book in candidate["books"]:
            evidence(book, now, 600)
            if book["promotional"] is not False:
                raise ValueError("Promotional or unknown sportsbook line type")
            if any(book[k] != candidate[k] for k in
                   ("event_id", "player_id", "sport", "market", "period", "line")):
                raise ValueError("Sportsbook identity, market, period or line mismatch")
            owner = BOOK_OWNERS.get(book["book"])
            if owner is None:
                raise ValueError("Unknown sportsbook operator")
            if owner in owners:
                continue
            owners.add(owner)
            over, under = number(book["over"], minimum=1.00001), number(book["under"], minimum=1.00001)
            total = 1/over + 1/under
            probability = (1/over if candidate["side"] == "over" else 1/under) / total
            comparisons.append({"book": book["book"], "owner": owner, "as_of": book["as_of"],
                                "over": over, "under": under, "no_vig_probability": probability})
        if len(owners) < 2:
            raise ValueError("At least two independent sportsbook operators required")
        model = estimate(checked, line, candidate["side"], opportunities, matchup,
                         min(b["no_vig_probability"] for b in comparisons))
        p = model["modeled_probability"]
        for book in comparisons:
            odds = book[candidate["side"]]
            book["reference_ev_per_unit"] = p * odds - 1
        result.update({"player": candidate["player"], "sport": candidate["sport"],
                       "side": candidate["side"], "line": line, "model": model,
                       "comparisons": comparisons, "context": context,
                       "prizepicks_ev": None,
                       "ev_note": "Individual PrizePicks EV unavailable: multi-pick payout and joint outcomes required.",
                       "reference_ev_per_unit": mean(b["reference_ev_per_unit"] for b in comparisons)})
        if p < .65:
            result["reasons"].append("Modeled probability below 65%")
        elif min(b["reference_ev_per_unit"] for b in comparisons) <= 0:
            result["reasons"].append("No positive reference EV at every comparison book")
        else:
            result["recommended"] = True
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError) as error:
        result["reasons"].append(str(error) if isinstance(error, ValueError) else "Missing or malformed required evidence")
    return result


def scan(candidates, now=None):
    if not isinstance(candidates, list):
        raise ValueError("Expected candidate array")
    results = [research(c, now) for c in candidates]
    return {"mode": "RESEARCH_ONLY", "as_of": (now or utcnow()).isoformat(),
            "model_warning": "Uncalibrated conservative heuristic, not a validated hit forecast.",
            "recommendations": [x for x in results if x["recommended"]], "audit": results}
