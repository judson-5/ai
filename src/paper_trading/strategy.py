"""Executable-side pricing, liquid quote filters and bounded option structures."""
from dataclasses import dataclass
from .market import Option


@dataclass(frozen=True)
class Leg:
    option: Option
    side: str


@dataclass(frozen=True)
class Plan:
    symbol: str
    strategy: str
    legs: tuple[Leg, ...]

    @property
    def contracts(self):
        return tuple(x.option.contract for x in self.legs)

    def economics(self, slippage=.01, fee=.65):
        # Unit cash flow: buys at ask+slippage, sells at bid-slippage.
        cash = sum((leg.option.bid-slippage if leg.side == "SELL"
                    else -leg.option.ask-slippage)*100 for leg in self.legs)
        fees = len(self.legs)*fee
        if len(self.legs) == 1:
            return {"entry_cash": cash-fees, "max_loss": -cash+2*fees}
        width = abs(self.legs[0].option.strike-self.legs[1].option.strike)*100
        if not 0 < cash < width:
            raise ValueError("Spread must have a positive credit smaller than width")
        return {"entry_cash": cash-fees, "max_loss": width-cash+2*fees+len(self.legs)*slippage*100}


def eligible(option, now, quantity=1):
    age = (now-option.timestamp).total_seconds()
    dte = (option.expiry-now).total_seconds()/86400
    mid = (option.ask+option.bid)/2
    return (0 <= age <= 60 and 7 <= dte <= 45 and option.bid > .01
            and option.ask >= option.bid and mid > 0
            and (option.ask-option.bid)/mid <= .15
            and min(option.bid_size, option.ask_size) >= quantity)


def validate_plan(plan):
    if plan.symbol not in {"SPY", "QQQ"} or any(l.option.underlying != plan.symbol for l in plan.legs):
        raise ValueError("Unsupported or mixed underlying")
    if len(plan.legs) == 1:
        leg = plan.legs[0]
        expected = "long_call" if leg.option.kind == "C" else "long_put"
        if leg.side != "BUY" or plan.strategy != expected:
            raise ValueError("Only long single options permitted")
    elif len(plan.legs) == 2:
        short, long = plan.legs
        if short.side != "SELL" or long.side != "BUY":
            raise ValueError("Spread must include protective long leg")
        a, b = short.option, long.option
        if a.kind != b.kind or a.expiry != b.expiry:
            raise ValueError("Spread legs must share type and expiry")
        if a.kind == "P":
            valid = plan.strategy == "put_credit_spread" and b.strike < a.strike
        else:
            valid = plan.strategy == "call_credit_spread" and b.strike > a.strike
        if not valid:
            raise ValueError("Invalid protective spread orientation")
    else:
        raise ValueError("Only long options and two-leg credit spreads")


def select(symbol, direction, options, now, style="long"):
    if style not in {"long", "credit"}:
        raise ValueError("Unknown option strategy style")
    if direction not in {"BULLISH", "BEARISH"}:
        return []
    kind = ("C" if direction == "BULLISH" else "P") if style == "long" else ("P" if direction == "BULLISH" else "C")
    chain = [o for o in options if o.underlying == symbol and o.kind == kind and eligible(o, now)]
    plans = []
    if style == "long":
        for option in chain:
            if .35 <= abs(option.delta) <= .65:
                plans.append(Plan(symbol, "long_call" if kind == "C" else "long_put", (Leg(option, "BUY"),)))
    else:
        for short in chain:
            if not .15 <= abs(short.delta) <= .35:
                continue
            for long in chain:
                protected = long.strike < short.strike if kind == "P" else long.strike > short.strike
                if long.expiry != short.expiry or not protected or abs(long.strike-short.strike) > 5:
                    continue
                plan = Plan(symbol, "put_credit_spread" if kind == "P" else "call_credit_spread",
                            (Leg(short, "SELL"), Leg(long, "BUY")))
                try:
                    plan.economics()
                except ValueError:
                    continue
                plans.append(plan)
    return sorted(plans, key=lambda p: (p.economics()["max_loss"], p.contracts))
