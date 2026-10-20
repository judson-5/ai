"""Reject nonfinite inputs, naive timestamps and undocumented missing values."""
from datetime import datetime, timezone
import math
import json
from pathlib import Path


def number(value, *, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Expected a finite JSON number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Expected a finite JSON number")
    if minimum is not None and result < minimum:
        raise ValueError("Number below minimum")
    if maximum is not None and result > maximum:
        raise ValueError("Number above maximum")
    return result


def stamp(value):
    if not isinstance(value, str):
        raise ValueError("Timestamp must be an ISO string")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timestamp must include timezone")
    return result.astimezone(timezone.utc)


def fresh(value, now, seconds):
    result = stamp(value)
    if not 0 <= (now - result).total_seconds() <= seconds:
        raise ValueError("Stale or future data")
    return result


def evidence(value, now, seconds=86400):
    if not isinstance(value, dict) or not value.get("source", "").startswith("https://"):
        raise ValueError("HTTPS source evidence required")
    fresh(value["as_of"], now, seconds)
    return value


def load(path):
    def reject(_):
        raise ValueError("Nonfinite JSON is forbidden")
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=reject)


def utcnow():
    return datetime.now(timezone.utc)
