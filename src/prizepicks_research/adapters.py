"""Authorized snapshot intake and The Odds API v4 read-only event odds."""
from urllib.parse import quote
from research_common.http import JsonGet, DataUnavailable, secret
from research_common.validation import load

# Originating operator identity, not the data aggregator. Unlisted books fail closed.
BOOK_OWNERS = {"draftkings": "draftkings", "fanduel": "flutter",
               "betmgm": "betmgm", "williamhill_us": "caesars",
               "caesars": "caesars", "espnbet": "penn", "thescorebet": "penn",
               "betrivers": "rushstreet", "bet365": "bet365"}
SPORTS = {"NBA": "basketball_nba", "WNBA": "basketball_wnba",
          "NFL": "americanfootball_nfl", "NCAAF": "americanfootball_ncaaf",
          "NCAAB": "basketball_ncaab", "MLB": "baseball_mlb", "NHL": "icehockey_nhl",
          "EPL": "soccer_epl"}
_BASKETBALL = {"player_points", "player_rebounds", "player_assists", "player_threes",
               "player_blocks", "player_steals", "player_turnovers", "player_points_rebounds_assists",
               "player_points_rebounds", "player_points_assists", "player_rebounds_assists"}
_FOOTBALL = {"player_pass_yds", "player_pass_tds", "player_pass_attempts", "player_pass_completions",
             "player_pass_interceptions", "player_rush_yds", "player_rush_attempts",
             "player_receptions", "player_reception_yds"}
MARKETS = {"NBA": _BASKETBALL, "WNBA": _BASKETBALL, "NCAAB": _BASKETBALL,
           "NFL": _FOOTBALL, "NCAAF": _FOOTBALL,
           "MLB": {"batter_hits", "batter_total_bases", "batter_home_runs", "batter_rbis",
                   "batter_runs_scored", "batter_strikeouts", "pitcher_strikeouts", "pitcher_outs"},
           "NHL": {"player_points", "player_goals", "player_assists", "player_shots_on_goal",
                   "player_blocked_shots", "player_total_saves"},
           "EPL": {"player_shots", "player_shots_on_target", "player_assists"}}


def read_snapshot(path):
    payload = load(path)
    if not isinstance(payload, list):
        raise ValueError("Snapshot must be an array of research candidates")
    return payload


class OddsApi:
    def __init__(self, transport=None):
        self.transport = transport or JsonGet("https://api.the-odds-api.com")

    def books(self, candidate):
        """Exact provider event/player/market mappings are supplied, never guessed."""
        sport = SPORTS[candidate["sport"]]
        if candidate["period"] != "full_game" or candidate["market"] not in MARKETS[candidate["sport"]]:
            raise ValueError("Unsupported full-game market mapping")
        event = quote(candidate["odds_event_id"], safe="")
        market = candidate["market"]
        payload = self.transport.get(f"/v4/sports/{sport}/events/{event}/odds", {
            "apiKey": secret("ODDS_API_KEY"), "regions": "us", "markets": market,
            "oddsFormat": "decimal"})
        if payload.get("id") != candidate["odds_event_id"] or payload.get("sport_key") != sport:
            raise DataUnavailable("Provider event mapping mismatch")
        if payload.get("commence_time") != candidate["event_start"]:
            # Compare instants, accommodating equivalent ISO formats.
            from research_common.validation import stamp
            if stamp(payload["commence_time"]) != stamp(candidate["event_start"]):
                raise DataUnavailable("Provider start time mismatch")
        results = []
        for book in payload.get("bookmakers", []):
            if book["key"] not in BOOK_OWNERS:
                continue
            for entry in book.get("markets", []):
                if entry["key"] != market:
                    continue
                matching = [o for o in entry.get("outcomes", [])
                            if o.get("description") == candidate["odds_player_name"]
                            and o.get("point") == candidate["line"]]
                sides = {o["name"].lower(): o["price"] for o in matching}
                if len(matching) != 2 or set(sides) != {"over", "under"}:
                    continue
                results.append({"book": book["key"], "event_id": candidate["event_id"],
                                "player_id": candidate["player_id"], "sport": candidate["sport"],
                                "market": market, "period": candidate["period"],
                                "line": candidate["line"], "over": sides["over"], "under": sides["under"],
                                "as_of": entry.get("last_update", book.get("last_update")),
                                "source": "https://api.the-odds-api.com/v4", "promotional": False})
        return results
