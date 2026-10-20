"""One-shot research, persistent local paper fills, and historical quote replay."""
import argparse
import json
from pathlib import Path
from uuid import uuid4
from research_common.validation import load, utcnow
from research_common.http import DataUnavailable
from .adapters import AlpacaData
from .indicators import analyze, NY
from .strategy import select
from .ledger import PaperLedger
from .replay import backtest, validate_capture, frame_data


def report(symbol, bars, options, now, style, feed):
    indicators = analyze(bars, now)
    plans = select(symbol, indicators["direction"], options, now, style)
    return {"mode": "PAPER_ONLY_RESEARCH", "as_of": now.isoformat(), "symbol": symbol,
            "option_feed": feed, "indicators": indicators,
            "plans": [{"strategy": p.strategy, "contracts": p.contracts,
                       **p.economics()} for p in plans]}, plans


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    live = commands.add_parser("analyze", help="Read Alpaca data; optionally simulate locally")
    live.add_argument("symbol", choices=["SPY", "QQQ"])
    live.add_argument("--style", choices=["long", "credit"], default="long")
    live.add_argument("--stock-feed", choices=["iex", "sip"], default="iex")
    live.add_argument("--option-feed", choices=["indicative", "opra"], default="indicative")
    live.add_argument("--capture", help="Save raw normalized provider evidence for replay")
    live.add_argument("--paper", action="store_true", help="Record a fill in local SQLite only")
    live.add_argument("--ledger", default="data/private/paper.sqlite3")
    live.add_argument("--trade-id", help="Stable ID for idempotent scheduled invocations")
    replay = commands.add_parser("backtest", help="Replay captured historical quotes")
    replay.add_argument("capture")
    replay.add_argument("--style", choices=["long", "credit"], default="long")
    replay.add_argument("--holding-minutes", type=int, default=5)
    merge = commands.add_parser("merge-captures", help="Combine matching single-symbol captures for replay")
    merge.add_argument("captures", nargs="+")
    merge.add_argument("--output", required=True)
    close = commands.add_parser("close", help="Close local position using a fresh captured quote frame")
    close.add_argument("trade_id")
    close.add_argument("capture")
    close.add_argument("--ledger", default="data/private/paper.sqlite3")
    status = commands.add_parser("status")
    status.add_argument("--ledger", default="data/private/paper.sqlite3")
    args = parser.parse_args()
    try:
        if args.command == "merge-captures":
            captures = [load(path) for path in args.captures]
            for capture in captures:
                validate_capture(capture)
            first = captures[0]
            keys = ("source", "symbol", "stock_feed", "option_feed")
            if any(any(p[k] != first[k] for k in keys) for p in captures):
                raise ValueError("Captures must share symbol, provider and feeds")
            from research_common.validation import stamp
            frames = sorted([f for p in captures for f in p["frames"]], key=lambda f: stamp(f["as_of"]))
            if len({stamp(f["as_of"]) for f in frames}) != len(frames):
                raise ValueError("Duplicate capture timestamps")
            combined = {**{k: first[k] for k in keys}, "frames": frames}
            for frame in frames:
                frame_data(combined, frame)
            destination = Path(args.output)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("x", encoding="utf-8") as handle:
                json.dump(combined, handle, indent=2, allow_nan=False)
            output = {"mode": "CAPTURE_MERGE", "frames": len(frames), "output": args.output}
        elif args.command == "backtest":
            output = backtest(load(args.capture), args.style, args.holding_minutes)
        elif args.command in {"close", "status"}:
            if not Path(args.ledger).is_file():
                raise ValueError("Paper ledger does not exist")
            ledger = PaperLedger(args.ledger)
            try:
                if args.command == "status":
                    output = {"mode": "PAPER_ONLY", "positions": ledger.positions()}
                else:
                    payload = load(args.capture)
                    validate_capture(payload, executions=True)
                    now, _, options = frame_data(payload, payload["frames"][-1])
                    # Interactive closure requires a current capture, not an old replay.
                    if not 0 <= (utcnow()-now).total_seconds() <= 60:
                        raise ValueError("Paper closure requires a current capture")
                    output = ledger.mark_close(args.trade_id, {o.contract: o for o in options}, now)
            finally:
                ledger.close()
        else:
            if args.paper and args.option_feed != "opra":
                raise ValueError("--paper requires --option-feed opra")
            now = utcnow()
            start = now.astimezone(NY).replace(hour=9, minute=30, second=0, microsecond=0)
            if now <= start:
                raise ValueError("Regular session has not opened")
            adapter = AlpacaData(stock_feed=args.stock_feed, option_feed=args.option_feed)
            bars = adapter.bars(args.symbol, start, now)
            from datetime import timedelta
            bars = [b for b in bars if b.timestamp+timedelta(minutes=1) <= now]
            options = adapter.options(args.symbol)
            # API responses can arrive after the initial clock read.
            now = utcnow()
            output, plans = report(args.symbol, bars, options, now, args.style, args.option_feed)
            output["stock_feed"] = args.stock_feed
            if args.capture:
                serialized_bars = [{"t": b.timestamp.isoformat(), "o": b.open, "h": b.high,
                                    "l": b.low, "c": b.close, "v": b.volume} for b in bars]
                snapshots = {o.contract: {"latestQuote": {"t": o.timestamp.isoformat(),
                              "bp": o.bid, "ap": o.ask, "bs": o.bid_size, "as": o.ask_size},
                              "greeks": {"delta": o.delta}} for o in options}
                capture = {"source": "alpaca", "symbol": args.symbol,
                           "stock_feed": args.stock_feed, "option_feed": args.option_feed,
                           "frames": [{"as_of": now.isoformat(), "bars": serialized_bars, "snapshots": snapshots}]}
                destination = Path(args.capture)
                destination.parent.mkdir(parents=True, exist_ok=True)
                # Exclusive creation prevents accidental destruction of captured history.
                with destination.open("x", encoding="utf-8") as handle:
                    json.dump(capture, handle, indent=2, allow_nan=False)
            if args.paper:
                Path(args.ledger).parent.mkdir(parents=True, exist_ok=True)
                ledger = PaperLedger(args.ledger)
                try:
                    output["paper_fills"] = []
                    output["risk_rejections"] = []
                    for plan in plans:
                        try:
                            fill = ledger.open(args.trade_id or str(uuid4()), plan, now)
                            output["paper_fills"].append(fill)
                            break
                        except ValueError as error:
                            output["risk_rejections"].append(str(error))
                finally:
                    ledger.close()
        print(json.dumps(output, indent=2, allow_nan=False))
    except (OSError, KeyError, ValueError, TypeError, DataUnavailable) as error:
        parser.exit(2, f"Research unavailable: {error}\n")


if __name__ == "__main__":
    main()
