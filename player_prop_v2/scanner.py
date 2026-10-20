"""Strict, fail-closed offline scanner for timestamped authorized data snapshots."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json
import math

MIN_PROB = 0.65
MIN_EV = 0.05

def iso(value):
    if not isinstance(value, str):
        raise ValueError("missing timestamp")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp must have timezone")
    return dt.astimezone(timezone.utc)

def validate(candidate, now=None):
    """Return result with explicit failures, never auto-approve speculative data."""
    now = now or datetime.now(timezone.utc)
    errors = []
    required = ("id", "player", "sport", "event_id", "market", "period",
                "line", "side", "as_of", "probability_lower", "books",
                "prizepicks_verified", "injury_cleared", "model_calibrated")
    for field in required:
        if field not in candidate:
            errors.append("missing_" + field)
    if errors:
        return {"id": candidate.get("id"), "qualifies": False, "reasons": errors}
    try:
        line = float(candidate["line"])
        prob = float(candidate["probability_lower"])
        stamp = iso(candidate["as_of"])
        if not (math.isfinite(line) and math.isfinite(prob) and 0 <= prob <= 1):
            errors.append("invalid_numeric")
        if candidate["side"] not in ("more", "less"):
            errors.append("invalid_side")
        if (now - stamp).total_seconds() > 600 or stamp > now:
            errors.append("stale_or_future_projection")
        if prob < MIN_PROB:
            errors.append("probability_below_65_pct")
        for key in ("prizepicks_verified", "injury_cleared", "model_calibrated"):
            if candidate[key] is not True:
                errors.append(key + "_not_verified")
        books = candidate["books"]
        unique = set()
        if not isinstance(books, list):
            errors.append("invalid_books")
        else:
            for book in books:
                try:
                    quote_time = iso(book["as_of"])
                    if (now - quote_time).total_seconds() > 600 or quote_time > now:
                        errors.append("stale_book_quote")
                    if (str(book["event_id"]), str(book["market"]), str(book["period"])) != (
                        str(candidate["event_id"]), str(candidate["market"]), str(candidate["period"])):
                        errors.append("mismatched_book_market")
                    if not math.isfinite(float(book["line"])):
                        errors.append("invalid_book_line")
                    if not book.get("provider"):
                        errors.append("missing_book_provider")
                    else:
                        unique.add(str(book["provider"]).casefold().strip())
                except (KeyError, ValueError, TypeError):
                    errors.append("invalid_book_quote")
            if len(unique) < 2:
                errors.append("fewer_than_two_independent_books")
        if candidate.get("lineup_ev") is None:
            errors.append("missing_verified_lineup_ev")
        else:
            ev = float(candidate["lineup_ev"])
            if not math.isfinite(ev) or ev < MIN_EV:
                errors.append("lineup_ev_below_5_pct_or_invalid")
            if candidate.get("actual_payout_verified") is not True:
                errors.append("payout_not_verified")
            if candidate.get("joint_probability_verified") is not True:
                errors.append("joint_probability_not_verified")
    except (ValueError, TypeError, KeyError, OverflowError):
        errors.append("malformed_candidate")
    return {"id": candidate.get("id"), "player": candidate.get("player"),
            "qualifies": not errors, "reasons": sorted(set(errors)),
            "probability_lower": candidate.get("probability_lower"),
            "lineup_ev": candidate.get("lineup_ev")}

def scan(records, now=None):
    results = [validate(item, now=now) for item in records]
    picks = [r for r in results if r["qualifies"]]
    picks.sort(key=lambda r: (r["probability_lower"], r["lineup_ev"]), reverse=True)
    return {"status": "QUALIFYING PICKS" if picks else "NO QUALIFYING PICKS",
            "examined": len(results), "qualified": picks[:10], "audit": results}

def scan_file(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("input must be a JSON array of candidate records")
    return scan(payload)
