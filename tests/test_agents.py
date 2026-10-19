import unittest
from datetime import datetime, timedelta
from agents.props import evaluate_prop
from agents.trading import Candle, PaperPortfolio, credit_spread_risk, ema, signal, vwap

class AgentTests(unittest.TestCase):
    def test_ema_constant(self):
        self.assertEqual(ema([5, 5, 5], 2), [5, 5, 5])
    def test_ema_invalid(self):
        with self.assertRaises(ValueError): ema([], 9)
    def test_vwap(self):
        c = Candle(datetime(2025,1,1), 10, 12, 9, 12, 100)
        self.assertAlmostEqual(vwap([c]), 11)
    def test_vwap_zero_volume(self):
        with self.assertRaises(ValueError):
            vwap([Candle(datetime(2025,1,1), 1, 1, 1, 1, 0)])
    def test_signal_short(self):
        self.assertEqual(signal([]), "NO_SIGNAL")
    def test_signal_uptrend(self):
        t = datetime(2025,1,1)
        cs = [Candle(t+timedelta(minutes=i),100+i,101+i,99+i,100+i,100) for i in range(40)]
        self.assertEqual(signal(cs), "BULLISH_WATCH")
    def test_credit_spread_risk(self):
        r = credit_spread_risk(5, 1, 1)
        self.assertEqual((r.max_profit, r.max_loss), (100, 400))
    def test_credit_spread_invalid(self):
        with self.assertRaises(ValueError): credit_spread_risk(5, 6)
    def test_paper_risk_limit(self):
        with self.assertRaises(ValueError):
            PaperPortfolio().open_paper_credit_spread("SPY",5,1)
    def test_paper_small_risk(self):
        p = PaperPortfolio()
        self.assertEqual(p.open_paper_credit_spread("QQQ", 1, 0.5)["mode"], "PAPER_ONLY")
    def test_prop_rate(self):
        r = evaluate_prop("Test", "points", 10.5, "over", [11]*10, 1.9)
        self.assertEqual(r.hit_rate, 1)
        self.assertLess(r.modeled_probability, 1)
    def test_prop_insufficient_sample(self):
        r = evaluate_prop("Test", "points", 10, "under", [9]*3, 2)
        self.assertFalse(r.qualifies)
    def test_prop_invalid_side(self):
        with self.assertRaises(ValueError):
            evaluate_prop("Test", "points", 10, "sideways", [9]*12, 2)

if __name__ == "__main__":
    unittest.main()
