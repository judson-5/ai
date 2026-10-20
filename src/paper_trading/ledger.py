"""Transactional SQLite local fills; no network or brokerage dependency."""
import json
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from .strategy import eligible, validate_plan
from .indicators import regular_session
from research_common.validation import number


class PaperLedger:
    def __init__(self, path, equity=10000, trade_fraction=.01, total_fraction=.05,
                 daily_loss_fraction=.02, slippage=.01, fee=.65):
        self.equity = number(equity, minimum=1)
        self.trade_fraction = number(trade_fraction, minimum=.00001, maximum=.02)
        self.total_fraction = number(total_fraction, minimum=self.trade_fraction, maximum=.1)
        self.daily_loss_fraction = number(daily_loss_fraction, minimum=.00001, maximum=.05)
        self.slippage, self.fee = number(slippage, minimum=0), number(fee, minimum=0)
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.execute("CREATE TABLE IF NOT EXISTS account (id INTEGER PRIMARY KEY CHECK(id=1), config TEXT NOT NULL)")
        config = json.dumps([equity, trade_fraction, total_fraction, daily_loss_fraction, slippage, fee])
        self.db.execute("INSERT OR IGNORE INTO account VALUES (1, ?)", (config,))
        if self.db.execute("SELECT config FROM account WHERE id=1").fetchone()[0] != config:
            self.db.close()
            raise ValueError("Existing ledger risk configuration differs")
        self.db.execute("""CREATE TABLE IF NOT EXISTS positions
          (id TEXT PRIMARY KEY, opened TEXT, closed TEXT, risk REAL, entry REAL,
           pnl REAL, payload TEXT)""")

    def close(self):
        self.db.close()

    def open(self, identifier, plan, now, quantity=1):
        validate_plan(plan)
        if type(quantity) is not int or quantity < 1:
            raise ValueError("Positive integer quantity required")
        if not identifier or now.tzinfo is None or not regular_session(now):
            raise ValueError("Identity and regular-session aware timestamp required")
        if any(not eligible(l.option, now, quantity) for l in plan.legs):
            raise ValueError("Option quote fails liquidity, freshness or expiration filter")
        prices = plan.economics(self.slippage, self.fee)
        risk = prices["max_loss"]*quantity
        payload = json.dumps({"mode": "PAPER_ONLY", "symbol": plan.symbol, "strategy": plan.strategy,
                              "quantity": quantity, "legs": [{"contract": l.option.contract,
                              "side": l.side, "expiry": l.option.expiry.isoformat()} for l in plan.legs]})
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self.db.execute("SELECT 1 FROM positions WHERE id=?", (identifier,)).fetchone():
                raise ValueError("Duplicate paper trade ID")
            rows = self.db.execute("SELECT closed, risk, pnl, payload FROM positions").fetchall()
            realized = sum(r[2] or 0 for r in rows)
            capital = min(self.equity, self.equity+realized)
            day = now.astimezone(ZoneInfo("America/New_York")).date()
            daily = sum(r[2] for r in rows if r[0] and datetime.fromisoformat(r[0]).astimezone(
                ZoneInfo("America/New_York")).date() == day)
            if capital <= 0 or daily <= -self.equity*self.daily_loss_fraction:
                raise ValueError("Paper daily loss or capital limit reached")
            active = [r for r in rows if r[0] is None]
            used = sum(r[1] for r in active)
            if daily-used-risk < -self.equity*self.daily_loss_fraction:
                raise ValueError("Remaining paper daily loss budget exceeded")
            if any(set(plan.contracts) & {l["contract"] for l in json.loads(r[3])["legs"]} for r in active):
                raise ValueError("Contract already held by an open paper position")
            if risk > capital*self.trade_fraction or used+risk > capital*self.total_fraction:
                raise ValueError("Paper risk budget exceeded")
            if risk > self.equity+realized-used:
                raise ValueError("Insufficient simulated capital")
            self.db.execute("INSERT INTO positions VALUES (?, ?, NULL, ?, ?, NULL, ?)",
                            (identifier, now.isoformat(), risk, prices["entry_cash"]*quantity, payload))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise
        return {"mode": "PAPER_ONLY", "id": identifier, "reserved_risk": risk,
                "entry_cash": prices["entry_cash"]*quantity}

    def mark_close(self, identifier, quotes, now):
        """Close against later same-contract quotes. No synthetic option prices."""
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT opened, closed, entry, payload, risk FROM positions WHERE id=?", (identifier,)).fetchone()
            if row is None or row[1] is not None:
                raise ValueError("Paper position missing or already closed")
            if now <= datetime.fromisoformat(row[0]):
                raise ValueError("Exit must follow entry")
            position = json.loads(row[3])
            exit_cash = 0
            for leg in position["legs"]:
                option = quotes.get(leg["contract"])
                if (option is None or option.contract != leg["contract"]
                        or not 0 <= (now-option.timestamp).total_seconds() <= 60
                        or option.timestamp <= datetime.fromisoformat(row[0])
                        or now >= datetime.fromisoformat(leg["expiry"])):
                    raise ValueError("Fresh post-entry, pre-expiry exit quote required")
                needed = option.bid_size if leg["side"] == "BUY" else option.ask_size
                if needed < position["quantity"]:
                    raise ValueError("Insufficient exit quote size")
                if leg["side"] == "BUY":
                    exit_cash += max(0, option.bid-self.slippage)*100-self.fee
                else:
                    exit_cash -= (option.ask+self.slippage)*100+self.fee
            pnl = row[2]+exit_cash*position["quantity"]
            if pnl < -row[4] - 1e-8:
                raise ValueError("Quoted exit exceeds reserved risk; no inferred fill")
            self.db.execute("UPDATE positions SET closed=?, pnl=? WHERE id=?", (now.isoformat(), pnl, identifier))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise
        return {"mode": "PAPER_ONLY", "id": identifier, "realized_pnl": pnl}

    def positions(self):
        return [{"id": r[0], "opened": r[1], "closed": r[2], "risk": r[3],
                 "entry": r[4], "pnl": r[5], **json.loads(r[6])}
                for r in self.db.execute("SELECT * FROM positions ORDER BY opened, id")]
