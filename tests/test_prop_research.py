"""Synthetic fixtures exercise safeguards; they are never presented as live data."""
from datetime import datetime, timedelta, timezone
import os
from unittest import TestCase
from unittest.mock import patch
from prizepicks_research.service import research, scan
from prizepicks_research.adapters import OddsApi
from prizepicks_research.model import wilson_lower

NOW = datetime(2026, 10, 20, 15, tzinfo=timezone.utc)


def candidate():
    common = {"sport": "NBA", "player_id": "synthetic-player", "event_id": "synthetic-event",
              "market": "player_points", "period": "full_game", "line": 20.5}
    return {**common, "id": "test", "player": "SYNTHETIC PLAYER", "side": "over",
            "source": "https://example.com/authorized-test", "as_of": NOW.isoformat(),
            "event_start": (NOW+timedelta(hours=3)).isoformat(), "promotional": False, "boosted": False,
            "context": {"source": "https://example.com/test-context", "as_of": NOW.isoformat(),
                        "injury_status": "available", "lineup_status": "confirmed",
                        "projected_opportunities": 32, "opportunity_unit": "minutes",
                        "matchup_factor": 1.0, "matchup_notes": "Synthetic neutral opponent"},
            "game_logs": [{"timestamp": (NOW-timedelta(days=i+1)).isoformat(), "game_id": str(i),
                           "source": "https://example.com/test-history", "value": 25,
                           "opportunities": 32} for i in range(30)],
            "books": [{**common, "book": book, "over": 1.9, "under": 1.9,
                       "source": "https://example.com/test-odds", "as_of": NOW.isoformat(),
                       "promotional": False} for book in ("draftkings", "fanduel")]}


class PropResearchTests(TestCase):
    def test_positive_research_and_distinct_ev(self):
        result = research(candidate(), NOW)
        self.assertTrue(result["recommended"], result)
        self.assertGreaterEqual(result["model"]["modeled_probability"], .65)
        self.assertIsNone(result["prizepicks_ev"])
        self.assertGreater(result["reference_ev_per_unit"], 0)

    def test_independent_operator_not_brand(self):
        c = candidate()
        c["books"][0]["book"], c["books"][1]["book"] = "caesars", "williamhill_us"
        self.assertFalse(research(c, NOW)["recommended"])

    def test_fail_closed_on_required_evidence(self):
        mutations = [lambda c: c.update(promotional=True), lambda c: c.update(boosted=True),
                     lambda c: c.pop("boosted"), lambda c: c.update(line=20),
                     lambda c: c.update(as_of=(NOW-timedelta(minutes=11)).isoformat()),
                     lambda c: c.update(as_of=(NOW+timedelta(seconds=1)).isoformat()),
                     lambda c: c["context"].update(injury_status="questionable"),
                     lambda c: c["context"].update(lineup_status="projected"),
                     lambda c: c["context"].update(projected_opportunities=float("nan")),
                     lambda c: c["books"][0].update(player_id="wrong"),
                     lambda c: c["books"][0].update(period="first_half"),
                     lambda c: c["books"][0].update(over=float("inf")),
                     lambda c: c["books"][0].update(promotional=True),
                     lambda c: c["books"][0].update(book="unknown"),
                     lambda c: c["books"].pop(),
                     lambda c: c.update(game_logs=c["game_logs"][:19]),
                     lambda c: c["game_logs"][0].update(timestamp=NOW.isoformat()),
                     lambda c: c["game_logs"][0].update(game_id="1")]
        for mutate in mutations:
            c = candidate()
            mutate(c)
            with self.subTest(mutate=mutate):
                self.assertFalse(research(c, NOW)["recommended"])

    def test_threshold_and_downside_opportunities(self):
        c = candidate()
        for log in c["game_logs"][:15]:
            log["value"] = 10
        self.assertFalse(research(c, NOW)["recommended"])

    def test_downside_opportunities(self):
        c = candidate()
        c["context"]["projected_opportunities"] = 10
        self.assertFalse(research(c, NOW)["recommended"])

    def test_exact_65_percent_gate(self):
        for probability, expected in [(.65, True), (.649999, False)]:
            with patch("prizepicks_research.service.estimate", return_value={"modeled_probability": probability}):
                self.assertEqual(research(candidate(), NOW)["recommended"], expected)

    def test_under_does_not_gain_confidence_from_reduced_opportunities(self):
        c = candidate()
        c["side"] = "under"
        c["context"]["projected_opportunities"] = 10
        self.assertFalse(research(c, NOW)["recommended"])

    def test_malformed_and_empty(self):
        self.assertFalse(research(None, NOW)["recommended"])
        self.assertEqual(scan([], NOW)["recommendations"], [])

    def test_wilson_bound(self):
        self.assertAlmostEqual(wilson_lower(30, 30), .91726, places=4)

    @patch.dict(os.environ, {"ODDS_API_KEY": "synthetic-test-secret"})
    def test_odds_api_contract_exact_player_line_and_event(self):
        class Fake:
            def get(self, path, params):
                self.path, self.params = path, params
                return {"id": "provider-event", "sport_key": "basketball_nba",
                        "commence_time": (NOW+timedelta(hours=3)).isoformat(),
                        "bookmakers": [{"key": "draftkings", "last_update": NOW.isoformat(),
                                        "markets": [{"key": "player_points", "outcomes": [
                                            {"description": "Provider Player", "point": 20.5, "name": side, "price": 1.9}
                                            for side in ["Over", "Under"]]}]}]}
        c, fake = candidate(), Fake()
        c.update(odds_event_id="provider-event", odds_player_name="Provider Player")
        books = OddsApi(fake).books(c)
        self.assertEqual(len(books), 1)
        self.assertEqual(fake.path, "/v4/sports/basketball_nba/events/provider-event/odds")
        self.assertEqual(books[0]["player_id"], c["player_id"])
        c["line"] = 21.5
        self.assertEqual(OddsApi(fake).books(c), [])
