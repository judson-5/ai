from datetime import datetime, timedelta, timezone
from dataclasses import replace
import tempfile
from pathlib import Path
from unittest import TestCase
from paper_trading.market import Bar, Option
from paper_trading.indicators import analyze
from paper_trading.strategy import select, Plan, Leg
from paper_trading.ledger import PaperLedger
from paper_trading.adapters import AlpacaData
from paper_trading.replay import backtest

START = datetime(2026, 10, 20, 13, 30, tzinfo=timezone.utc)
NOW = START+timedelta(minutes=30)


def bars(count=30):
    return [Bar.parse("SPY", {"t": (START+timedelta(minutes=i)).isoformat(),
                             "o": 500+i, "h": 501+i, "l": 499+i, "c": 500+i,
                             "v": 1500 if i >= 29 else 1000}) for i in range(count)]


def option(contract="SPY261120C00530000", bid=.70, ask=.75, delta=.5, now=NOW):
    return Option.parse(contract, {"latestQuote": {"bp": bid, "ap": ask, "bs": 10,
                        "as": 10, "t": now.isoformat()}, "greeks": {"delta": delta}})


def capture(frames=2):
    output = {"source": "alpaca", "symbol": "SPY", "stock_feed": "sip", "option_feed": "opra", "frames": []}
    for i in range(frames):
        now = NOW+timedelta(minutes=i*5)
        history = bars(30+i*5)
        output["frames"].append({"as_of": now.isoformat(),
            "bars": [{"t": b.timestamp.isoformat(), "o": b.open, "h": b.high, "l": b.low,
                      "c": b.close, "v": b.volume} for b in history],
            "snapshots": {"SPY261120C00530000": {"latestQuote": {"bp": .70+i*.1,
                          "ap": .75+i*.1, "bs": 10, "as": 10, "t": now.isoformat()},
                          "greeks": {"delta": .5}}}})
    return output


class IndicatorTests(TestCase):
    def test_all_four_filters(self):
        self.assertEqual(analyze(bars(), NOW)["direction"], "BULLISH")
        flat_volume = [replace(b, volume=1000) for b in bars()]
        self.assertEqual(analyze(flat_volume, NOW)["direction"], "NONE")

    def test_session_reset_missing_and_unfinished(self):
        history = bars()
        self.assertEqual(analyze(history[1:], NOW)["direction"], "NONE")
        self.assertEqual(analyze(history[:10]+history[11:], NOW)["direction"], "NONE")
        self.assertEqual(analyze(history, NOW-timedelta(seconds=1))["direction"], "NONE")
        self.assertEqual(analyze(history, NOW+timedelta(minutes=4))["direction"], "NONE")

    def test_bad_bars(self):
        for value in [float("nan"), float("inf"), -1]:
            with self.assertRaises(ValueError):
                Bar.parse("SPY", {"t": NOW.isoformat(), "o": value, "h": 1, "l": 1, "c": 1, "v": 1})
        with self.assertRaises(ValueError):
            analyze(bars()+bars(), NOW)


class OptionRiskTests(TestCase):
    def setUp(self):
        self.ledger = PaperLedger(":memory:")
        self.addCleanup(self.ledger.close)

    def test_long_call_put_and_credit_spreads(self):
        call = select("SPY", "BULLISH", [option()], NOW)[0]
        put = select("SPY", "BEARISH", [option("SPY261120P00530000", delta=-.5)], NOW)[0]
        self.assertEqual((call.strategy, put.strategy), ("long_call", "long_put"))
        chain = [option("SPY261120P00530000", bid=.75, ask=.8, delta=-.25),
                 option("SPY261120P00529000", bid=.3, ask=.34, delta=-.1)]
        spreads = select("SPY", "BULLISH", chain, NOW, "credit")
        self.assertEqual(spreads[0].strategy, "put_credit_spread")
        self.assertGreater(spreads[0].economics()["max_loss"], 0)
        calls = [option("SPY261120C00530000", bid=.75, ask=.8, delta=.25),
                 option("SPY261120C00531000", bid=.3, ask=.34, delta=.1)]
        self.assertEqual(select("SPY", "BEARISH", calls, NOW, "credit")[0].strategy, "call_credit_spread")

    def test_quote_filters(self):
        for quote in [replace(option(), timestamp=NOW-timedelta(seconds=61)),
                      replace(option(), timestamp=NOW+timedelta(seconds=1)),
                      replace(option(), ask=2), replace(option(), bid_size=0),
                      option("SPY261021C00530000")]:
            self.assertEqual(select("SPY", "BULLISH", [quote], NOW), [])

    def test_risk_quantity_and_no_naked_shorts(self):
        plan = select("SPY", "BULLISH", [option()], NOW)[0]
        for qty in [0, 1.5, True, 10]:
            with self.assertRaises(ValueError):
                self.ledger.open("test", plan, NOW, qty)
        with self.assertRaises(ValueError):
            self.ledger.open("naked", Plan("SPY", "long_call", (Leg(option(), "SELL"),)), NOW)
        self.assertEqual(self.ledger.open("test", plan, NOW)["mode"], "PAPER_ONLY")
        with self.assertRaises(ValueError):
            self.ledger.open("test", plan, NOW)
        with self.assertRaises(ValueError):
            self.ledger.open("another", plan, NOW)

    def test_close_pnl_fees_and_release_risk(self):
        plan = select("SPY", "BULLISH", [option()], NOW)[0]
        self.ledger.open("one", plan, NOW)
        later = NOW+timedelta(minutes=5)
        quote = option(bid=.9, ask=.95, now=later)
        result = self.ledger.mark_close("one", {quote.contract: quote}, later)
        self.assertAlmostEqual(result["realized_pnl"], 11.7)
        with self.assertRaises(ValueError):
            self.ledger.mark_close("one", {quote.contract: quote}, later)

    def test_missing_exit_keeps_position_open(self):
        plan = select("SPY", "BULLISH", [option()], NOW)[0]
        self.ledger.open("one", plan, NOW)
        with self.assertRaises(ValueError):
            self.ledger.mark_close("one", {}, NOW+timedelta(minutes=5))
        self.assertIsNone(self.ledger.positions()[0]["closed"])

    def test_ledger_survives_restart_and_configuration_pinned(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"paper.sqlite3"
            ledger = PaperLedger(path)
            ledger.open("persist", select("SPY", "BULLISH", [option()], NOW)[0], NOW)
            ledger.close()
            again = PaperLedger(path)
            self.assertEqual(again.positions()[0]["id"], "persist")
            again.close()
            with self.assertRaises(ValueError):
                PaperLedger(path, equity=100000)

    def test_daily_budget(self):
        for i, contract in enumerate(["SPY261120C00530000", "SPY261120C00531000", "SPY261120C00532000"]):
            plan = select("SPY", "BULLISH", [option(contract)], NOW)[0]
            if i < 2:
                self.ledger.open(str(i), plan, NOW)
            else:
                with self.assertRaises(ValueError):
                    self.ledger.open(str(i), plan, NOW)


class ReplayTests(TestCase):
    def test_real_quote_round_trip(self):
        result = backtest(capture())
        self.assertEqual(result["closed_trades"], 1)
        self.assertAlmostEqual(result["realized_pnl"], 1.7)

    def test_missing_exit_is_unresolved(self):
        data = capture()
        data["frames"][1]["snapshots"] = {}
        result = backtest(data)
        self.assertEqual(result["closed_trades"], 0)
        self.assertEqual(result["unresolved_positions"], 1)

    def test_no_lookahead_revisions_or_indicative_fills(self):
        for case in ["future_bar", "future_quote", "revision", "order", "indicative"]:
            data = capture()
            if case == "future_bar":
                data["frames"][0]["bars"][-1]["t"] = (NOW+timedelta(minutes=1)).isoformat()
            elif case == "future_quote":
                data["frames"][0]["snapshots"]["SPY261120C00530000"]["latestQuote"]["t"] = (NOW+timedelta(seconds=1)).isoformat()
            elif case == "revision":
                data["frames"][1]["bars"][0]["v"] += 1
            elif case == "order":
                data["frames"].reverse()
            else:
                data["option_feed"] = "indicative"
            with self.subTest(case=case), self.assertRaises(ValueError):
                backtest(data)


class AdapterTests(TestCase):
    def test_read_only_paths_pagination_and_option_contract(self):
        class Fake:
            def __init__(self):
                self.paths = []
            def get(self, path, params):
                self.paths.append(path)
                if "stocks" in path:
                    index = 1 if params.get("page_token") else 0
                    b = bars()[index]
                    return {"bars": {"SPY": [{"t": b.timestamp.isoformat(), "o": b.open, "h": b.high,
                             "l": b.low, "c": b.close, "v": b.volume}]}, "next_page_token": None if index else "next"}
                return {"snapshots": capture()["frames"][0]["snapshots"]}
        fake = Fake()
        adapter = AlpacaData(fake)
        self.assertEqual(len(adapter.bars("SPY", START, NOW)), 2)
        self.assertEqual(adapter.options("SPY")[0].underlying, "SPY")
        self.assertEqual(fake.paths[-1], "/v1beta1/options/snapshots/SPY")
        self.assertFalse(hasattr(adapter, "submit_order"))

    def test_repeated_pagination_refused(self):
        class Fake:
            def get(self, path, params):
                return {"bars": {}, "next_page_token": "same"}
        with self.assertRaises(Exception) as context:
            AlpacaData(Fake()).bars("SPY", START, NOW)
        self.assertIn("Repeated", str(context.exception))
