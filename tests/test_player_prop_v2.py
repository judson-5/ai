import unittest
from datetime import datetime, timezone
from player_prop_v2.scanner import scan, validate

NOW = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)
def candidate():
    stamp = "2026-10-20T14:59:00+00:00"
    return dict(id="t", player="Example", sport="NBA", event_id="g1", market="points",
        period="full_game", line=20.5, side="more", as_of=stamp,
        probability_lower=.70, prizepicks_verified=True, injury_cleared=True,
        model_calibrated=True, lineup_ev=.08, actual_payout_verified=True,
        joint_probability_verified=True,
        books=[dict(provider=p, event_id="g1", market="points",
                    period="full_game", line=20.5, as_of=stamp)
               for p in ("bookA", "bookB")])
class TestStrictScanner(unittest.TestCase):
    def test_qualified_research_record(self):
        self.assertTrue(validate(candidate(), NOW)["qualifies"])
    def test_probability_threshold(self):
        c = candidate(); c["probability_lower"] = .649
        self.assertFalse(validate(c, NOW)["qualifies"])
    def test_ev_threshold(self):
        c = candidate(); c["lineup_ev"] = .049
        self.assertFalse(validate(c, NOW)["qualifies"])
    def test_not_two_books(self):
        c = candidate(); c["books"][1]["provider"] = "bookA"
        self.assertFalse(validate(c, NOW)["qualifies"])
    def test_no_unverified_payout(self):
        c = candidate(); c["actual_payout_verified"] = False
        self.assertFalse(validate(c, NOW)["qualifies"])
    def test_stale_quote(self):
        c = candidate(); c["books"][0]["as_of"] = "2020-01-01T00:00:00+00:00"
        self.assertFalse(validate(c, NOW)["qualifies"])
    def test_empty_list(self):
        self.assertEqual(scan([])["status"], "NO QUALIFYING PICKS")
if __name__ == "__main__":
    unittest.main()
