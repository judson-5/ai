"""Completed regular-session 1-minute bars; session-reset VWAP and volume gate."""
from datetime import timedelta
from zoneinfo import ZoneInfo
from .market import ordered_bars

NY = ZoneInfo("America/New_York")


def ema(values, period):
    out = [values[0]]
    alpha = 2/(period+1)
    for value in values[1:]:
        out.append(alpha*value + (1-alpha)*out[-1])
    return out


def regular_session(timestamp):
    local = timestamp.astimezone(NY)
    return local.weekday() < 5 and (9, 30) <= (local.hour, local.minute) < (16, 0)


def analyze(bars, now):
    ordered_bars(bars)
    if now.tzinfo is None:
        raise ValueError("Timezone-aware decision time required")
    today = now.astimezone(NY).date()
    session = [b for b in bars if regular_session(b.timestamp)
               and b.timestamp.astimezone(NY).date() == today
               and b.timestamp + timedelta(minutes=1) <= now]
    base = {"direction": "NONE", "reason": "Insufficient completed session history"}
    if len(session) < 30:
        return base
    first = session[0].timestamp.astimezone(NY)
    if (first.hour, first.minute, first.second) != (9, 30, 0):
        return {**base, "reason": "Session-open data required for VWAP"}
    if any(b.timestamp-a.timestamp != timedelta(minutes=1) for a, b in zip(session, session[1:])):
        return {**base, "reason": "Missing one-minute bars"}
    if not regular_session(now) or (now-session[-1].timestamp).total_seconds() > 125:
        return {**base, "reason": "Closed session or stale bars"}
    closes = [b.close for b in session]
    fast, slow = ema(closes, 9), ema(closes, 21)
    volume = sum(b.volume for b in session)
    baseline = sum(b.volume for b in session[-21:-1])/20
    if volume <= 0 or baseline <= 0:
        return {**base, "reason": "Insufficient volume"}
    vwap = sum((b.high+b.low+b.close)/3*b.volume for b in session)/volume
    momentum = closes[-1]/closes[-6]-1
    ratio = session[-1].volume/baseline
    direction = "NONE"
    if ratio >= 1.2:
        if closes[-1] > fast[-1] > slow[-1] and closes[-1] > vwap and momentum > 0:
            direction = "BULLISH"
        elif closes[-1] < fast[-1] < slow[-1] and closes[-1] < vwap and momentum < 0:
            direction = "BEARISH"
    return {"direction": direction, "ema9": fast[-1], "ema21": slow[-1],
            "vwap": vwap, "momentum_5m": momentum, "volume_ratio": ratio,
            "bar_timestamp": session[-1].timestamp.isoformat(),
            "reason": "Trend, VWAP, momentum and volume alignment" if direction != "NONE" else "Filters not aligned"}
