"""Demonstration on synthetic values only. No current quotes."""
from datetime import datetime, timedelta
from .props import evaluate_prop
from .trading import Candle, PaperPortfolio, signal

def main():
    report = evaluate_prop("Example Player", "points", 19.5, "over",
                           [20, 21, 23, 19, 25, 20, 24, 17, 22, 26, 20, 21], 1.91)
    print("SYNTHETIC prop evaluation:", report)
    start = datetime(2025, 1, 1, 9, 30)
    candles = [Candle(start + timedelta(minutes=i), 100+i*0.1, 100.2+i*0.1,
                      99.8+i*0.1, 100+i*0.1, 1000) for i in range(40)]
    print("SYNTHETIC trend signal:", signal(candles))
    print("PAPER ONLY:", PaperPortfolio().open_paper_credit_spread("SPY", 5, 1))

if __name__ == "__main__":
    main()
