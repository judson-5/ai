# Player Prop Edge Scanner V2 — Codespaces starter

**Research-only.** This add-on leaves the existing `agents/trading.py` and original prop scanner untouched. It does not access live PrizePicks accounts, request or submit wagers, or produce genuine predictions from synthetic samples.

## In GitHub Codespaces terminal
```bash
python -m unittest discover -s tests -v
python -m player_prop_v2
python -m player_prop_v2 data/private/validated_candidates.json
```
The included sample is fictional and intentionally fails the strict verification gates.

## Candidate JSON contract
Provide a JSON array of candidate objects with:
- `id, player, sport, event_id, market, period, line, side, as_of`
- `probability_lower`: a **calibrated conservative probability**, not L5/L10 frequency
- `books`: quotes from two distinct originating books with `provider, event_id, market, period, line, as_of`
- `prizepicks_verified, injury_cleared, model_calibrated`: true only with supporting source evidence
- `lineup_ev`: derived from a separately verified joint outcome distribution and actual payout schedule
- `actual_payout_verified, joint_probability_verified`: true only when substantiated

Timestamps must include a UTC offset. Quotes older than ten minutes fail.

## What is and is not implemented
Implemented: normalization gates, quote freshness, two-book origin test, minimum 65% conservative probability and +5% full-entry EV checks, rejection reasons, CLI, tests.

**Not implemented:** licensed live provider ingestion, sports-specific calibrated forecasting, actual payout collection, injury webhooks, closing-line history, independent correlation modeling or automatic Codespaces startup. These require provider credentials, source rights, tested algorithms and infrastructure. Do not mark verification flags true unless the work has actually been done.

Codespaces can open the project, but a GitHub browser user must create/start a Codespace if none exists. For production, store credentials in Codespaces secrets — never committed files.
