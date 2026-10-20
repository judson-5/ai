"""Quote-driven walk-forward replay; missing exit quotes remain unresolved."""
from datetime import timedelta
from research_common.validation import stamp, number
from .market import Bar, Option, ordered_bars
from .indicators import analyze
from .strategy import select
from .ledger import PaperLedger


def validate_capture(payload, *, executions=False):
    if (not isinstance(payload, dict) or payload["source"] != "alpaca"
            or payload["symbol"] not in {"SPY", "QQQ"}
            or payload["stock_feed"] not in {"iex", "sip"}
            or payload["option_feed"] not in {"opra", "indicative"}):
        raise ValueError("Capture must identify Alpaca, SPY/QQQ and actual data feeds")
    if executions and payload["option_feed"] != "opra":
        raise ValueError("OPRA quotes required for paper fills and backtesting")
    if not isinstance(payload["frames"], list) or not payload["frames"]:
        raise ValueError("At least one captured frame required")


def frame_data(payload, frame):
    now = stamp(frame["as_of"])
    bars = [Bar.parse(payload["symbol"], b) for b in frame["bars"]]
    ordered_bars(bars)
    if any(b.timestamp+timedelta(minutes=1) > now for b in bars):
        raise ValueError("Replay contains an incomplete or future bar")
    options = [Option.parse(key, row) for key, row in frame["snapshots"].items()]
    if any(o.timestamp > now or o.underlying != payload["symbol"] for o in options):
        raise ValueError("Replay contains future or mismatched option quotes")
    return now, bars, options


def backtest(payload, style="long", holding_minutes=5):
    validate_capture(payload, executions=True)
    if type(holding_minutes) is not int or holding_minutes < 1:
        raise ValueError("Positive holding period required")
    ledger = PaperLedger(":memory:")
    last_time, last_bars, active, warnings = None, {}, None, []
    peak, max_drawdown, equity_curve = ledger.equity, 0, []
    try:
        for index, frame in enumerate(payload["frames"]):
            now, bars, options = frame_data(payload, frame)
            if last_time is not None and now <= last_time:
                raise ValueError("Replay frames must be strictly chronological")
            last_time = now
            for bar in bars:
                previous = last_bars.get(bar.timestamp)
                if previous is not None and previous != bar:
                    raise ValueError("Historical bars changed during replay")
                last_bars[bar.timestamp] = bar
            # Decisions cannot access the future frame; exits use later actual quotes.
            if active is not None and now >= active[1]+timedelta(minutes=holding_minutes):
                try:
                    ledger.mark_close(active[0], {o.contract: o for o in options}, now)
                    active = None
                except ValueError:
                    warnings.append({"frame": index, "reason": "Exit unavailable; position and risk remain open"})
            direction = analyze(bars, now)["direction"]
            if active is None:
                plans = select(payload["symbol"], direction, options, now, style)
                for plan in plans:
                    try:
                        identifier = f"replay-{index}"
                        ledger.open(identifier, plan, now)
                        active = identifier, now
                        break
                    except ValueError:
                        continue
            realized = sum(p["pnl"] or 0 for p in ledger.positions())
            current = ledger.equity+realized
            peak = max(peak, current)
            max_drawdown = max(max_drawdown, peak-current)
            equity_curve.append({"as_of": now.isoformat(), "realized_equity": current})
        positions = ledger.positions()
        closed = [p for p in positions if p["closed"]]
        return {"mode": "PAPER_ONLY_BACKTEST", "stock_feed": payload["stock_feed"],
                "option_feed": payload["option_feed"], "trades": positions,
                "closed_trades": len(closed), "unresolved_positions": sum(p["closed"] is None for p in positions),
                "realized_pnl": sum(p["pnl"] for p in closed),
                "win_rate": sum(p["pnl"] > 0 for p in closed)/len(closed) if closed else None,
                "max_realized_drawdown": max_drawdown, "equity_curve": equity_curve,
                "warnings": warnings,
                "limitations": "Realized drawdown excludes open-position marks. No assignment, expiry settlement or queue simulation. Missing quotes never receive inferred fills."}
    finally:
        ledger.close()
