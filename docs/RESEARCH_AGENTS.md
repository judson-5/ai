# Operating the two research applications

Python 3.11+; no third-party runtime libraries. `pyproject.toml` manages packaging
and console commands. Build isolation needs setuptools (bounded in that file).
All network calls use TLS and bounded, GET-only requests. No wagering, payment,
broker account or order submission API exists in either new application.

## Installation in Codespaces on iPhone

1. Open this repository in Safari. Select the implementation branch (or main after
   its PR is merged), then **Code → Codespaces → Create codespace**. Use Safari's
   **Request Desktop Website** if needed. An existing Codespace on main will need
   `git fetch origin` and `git switch feat/research-agents` before the merge.
2. Open the terminal using **Terminal → New Terminal** in the browser editor.
   The dev container installs the project and runs tests automatically.
3. If using an existing Codespace or another Python environment, run:

   ```sh
   python -m venv .venv
   . .venv/bin/activate
   python -m pip install -e .
   python -m unittest discover -s tests -v
   ```

4. Add provider keys through **GitHub Settings → Codespaces → Secrets**, grant
   access only to `judson-5/ai`, then restart the Codespace. See [SECRETS.md](SECRETS.md).
   Offline tests need no keys. No paid provider access is purchased by this code.

Commands can be pasted into the mobile terminal. Reports print JSON; add
`> reports/name.json` after first creating `reports/` to save them. Keep raw data,
captures, ledgers and provider exports in ignored `data/private/`.

## Agent 1: PrizePicks research

```sh
mkdir -p data/private reports
cp data/templates/prizepicks_research.json data/private/props.json
# Replace template placeholders with authorized, timestamped evidence first.
python -m prizepicks_research data/private/props.json
# Optional: replace supplied sportsbook quotes with current The Odds API quotes.
python -m prizepicks_research data/private/props.json --refresh-books
```

There is no documented, authenticated PrizePicks feed configured here. The agent
accepts authorized exports/snapshots rather than inventing a private endpoint or
scraping one. It does not automatically discover PrizePicks lines, injuries,
game logs or lineups. You must obtain these from licensed sources. Empty or
incomplete evidence produces no recommendation, with a reason for each candidate.
A failed sportsbook refresh clears supplied quotes rather than reusing them.

Supported sport mappings: NBA, WNBA, NFL, NCAAF, NCAAB, MLB, NHL, EPL. Availability
of individual player markets depends on provider coverage and subscription.
Only explicitly mapped pregame full-game markets and noninteger lines are
supported; integer pushes need a separate settlement model. Market identifiers
must match the provider, such as `player_points`, not an approximate display label.

### Snapshot contract

Input is a JSON array; each candidate has:

| Field | Required meaning |
| --- | --- |
| `id`, `player`, `player_id`, `event_id` | Nonempty stable identifiers/names |
| `sport`, `market`, `period` | Supported sport, exact market key, `full_game` |
| `line`, `side` | Nonnegative finite noninteger line; `over` or `under` |
| `source`, `as_of`, `event_start` | HTTPS provenance, offset-aware capture time and future event start |
| `promotional`, `boosted` | Explicit JSON `false`; unknown types are rejected |
| `context` | Evidence object described below |
| `game_logs` | At least 20 sourced, completed historical games |
| `books` | At least two independent operators' same-line two-sided odds |
| `odds_event_id`, `odds_player_name` | Exact provider mapping when using `--refresh-books` |

`context` requires HTTPS `source`, `as_of` within 24 hours, `injury_status` equal
to `available`, `lineup_status` equal to `confirmed`, positive
`projected_opportunities`, `opportunity_unit` (e.g. minutes, carries, plate
appearances), `matchup_factor` in [0.5, 1.5], and `matchup_notes`. The factor is a
sourced forecast multiplier, not a fabricated opponent adjustment. Split inputs
into separate candidates when opportunity units differ. A source URL records
provenance; the application cannot certify the truth of an uploaded file.

Each log has `game_id`, offset-aware `timestamp`, HTTPS `source`, nonnegative
numeric `value` and positive numeric `opportunities` in the same unit as context.
Duplicate game IDs, current/future games, and missing values fail. The last game
must be within 45 days. Most recent 30 games are used, sorted by timestamp.

Each book has `book` (operator key), `event_id`, `player_id`, `sport`, `market`,
`period`, `line`, decimal `over` and `under` prices >1, HTTPS `source`, `as_of`,
and `promotional: false`. Every identity, period and line must match. Quotes and
PrizePicks observations expire after 10 minutes; future timestamps fail.
Sportsbooks are deduplicated by parent operator, not feed name. The explicit
registry is in `prizepicks_research/adapters.py`; unknown operators fail closed.
Caesars/William Hill and ESPN Bet/theScore Bet each count as one owner. Ownership
must be reviewed when operators change. The Odds API is one aggregator carrying
two independently originating book prices, not two independent aggregators.
Only its standard nonpromotional event markets are ingested.

### Probability and EV interpretation

The model calculates a one-sided 95% Wilson lower bound on recent strict wins;
equal historical values are non-wins. It reduces historical output for lower
projected opportunities and unfavorable matchups, never raises it, and takes the
minimum of adjusted and unadjusted lower bounds. This prevents an under from
gaining artificial confidence from a simple scaling assumption. It then shrinks
the lower bound 25% toward the lowest same-side no-vig sportsbook estimate when
that estimate is lower. The sportsbook estimate is normalized from both sides.

Research recommendations require modeled probability **≥65%** and positive
reference EV at **each** comparison book, after all data gates pass. Reference
EV per unit is `p * decimal_price - 1`; it is not a PrizePicks payout. The report
keeps `prizepicks_ev` null: a multi-pick entry requires the actual payout schedule,
push/void rules, and a justified joint outcome model. Never multiply marginal
probabilities while assuming independence. There is no fabricated joint EV.

This is a conservative research heuristic, **not a calibrated sports forecast**.
The Wilson bound covers sampling error under historical assumptions, not injury,
selection bias or regime error. Before relying on its probabilities, evaluate
held-out, time-ordered predictions by sport/market (reliability bins, Brier score,
sample sizes and closing-line movement). A 65% model output is not a guarantee.

## Agent 2: SPY/QQQ local paper trading

```sh
# Research only; IEX stock feed and indicative options are labeled in output.
python -m paper_trading analyze SPY --style long
python -m paper_trading analyze QQQ --style credit
# Real-time OPRA subscription/entitlement required; only a local SQLite fill.
python -m paper_trading analyze SPY --option-feed opra --stock-feed sip \
  --paper --style long --trade-id spy-session-001 \
  --capture data/private/spy-001.json
python -m paper_trading status
```

One invocation performs one decision cycle. No unattended broker process is
installed. For scheduled local paper cycles, use a stable unique `--trade-id`
for each intended decision to prevent duplicate fills. Only one eligible plan
is opened per invocation. SQLite transactions reserve risk across processes.
No broker URL, trading mode switch or live order method is present. API keys are
used only at `data.alpaca.markets`; even live-account credentials cannot route
orders through this application.

Signals require 30 completed chronological one-minute bars starting at 09:30
America/New_York with no gaps, session VWAP, EMA9/EMA21 alignment, same-direction
five-minute momentum, and final volume ≥1.2× the prior 20-bar average. VWAP and
EMAs restart each session. Incomplete bars are excluded; stale bars stop signals.
The window is weekdays 09:30–16:00 Eastern, DST-aware. There is no exchange
holiday/early-close calendar: current-data freshness still gates signals, but
operators must avoid scheduling on closed or shortened sessions. IEX volume
is partial market volume; SIP requires entitlement. Signals are feed-dependent.

Options require a fresh (≤60s), positive, uncrossed quote; relative bid/ask spread
≤15%; displayed sizes sufficient for quantity; and 7–45 days until expiration.
Long calls/puts use absolute delta .35–.65. Bullish credit spreads sell puts;
bearish spreads sell calls, short absolute delta .15–.35, with protective same-type,
same-expiry long legs, widths ≤$5 and positive net credit below width. Naked short
legs and mixed symbols/expirations fail validation. Open interest is not assumed
available: liquidity uses quote spread/size, not invented OI/volume.

Fills buy at ask+$0.01 and sell at bid−$0.01, with $0.65 per leg per side. Options
use a 100-share multiplier. Defaults: $10,000 starting paper capital, 1% maximum
trade risk, 5% aggregate risk, and 2% daily realized-plus-reserved loss budget.
Realized losses lower sizing capital; gains do not increase it. Risk includes
round-trip fees and conservative spread exit slippage. Duplicate open contracts
are rejected. Ledger configuration is pinned on creation, so a restart cannot
reset or inflate the account. Library callers may supply stricter risk parameters.

To close a local position, obtain a **later current OPRA capture** containing
every held contract, then run:

```sh
python -m paper_trading analyze SPY --option-feed opra \
  --capture data/private/spy-exit.json
python -m paper_trading close spy-session-001 data/private/spy-exit.json
```

Closes require fresh post-entry, pre-expiry quotes and sufficient displayed size.
An unavailable or dislocated exit leaves the position open with risk reserved.
There is no automatic expiry settlement or assignment simulation. Monitor and
close paper positions before expiration; do not mistake an unresolved position
for a zero loss. Use `status` to inspect the persisted ledger.

### Backtesting recorded options

Capture multiple decision frames during market hours using distinct filenames,
then combine them for the **same symbol and same feeds**:

```sh
python -m paper_trading merge-captures data/private/spy-001.json \
  data/private/spy-exit.json --output data/private/spy-replay.json
python -m paper_trading backtest data/private/spy-replay.json --style long \
  --holding-minutes 5
python -m paper_trading backtest data/private/spy-replay.json --style credit
```

Capture format: `{source: "alpaca", symbol: "SPY", stock_feed: "sip",
option_feed: "opra", frames: [...]}`. Each frame has offset-aware `as_of`,
`bars` (Alpaca `t,o,h,l,c,v` fields, session history through the decision), and
`snapshots` keyed by OCC contract with `latestQuote` (`t,bp,ap,bs,as`) and
`greeks.delta`. CLI capture files use this format directly. External imports
must retain their actual provider/feed identifiers and timestamps. Edited files
are not cryptographically verified. Never relabel synthetic or indicative data
as OPRA. Indicative feeds are research-only and cannot receive paper fills.

Replay uses only completed data available at each frame, rejects future quotes,
out-of-order/duplicate times and revised historical bars, and waits at least the
holding period for an exit. Only one position is active per replay. Missing exits
remain unresolved and do not fabricate realized profit. Backtests start a fresh
in-memory ledger and cannot affect the persistent paper account. Output includes
trades, fees/slippage-adjusted realized P&L, win rate, realized equity curve and
**realized** maximum drawdown. Open losses are excluded from that drawdown, so
inspect unresolved positions before interpreting results. There is no underlying
return proxy masquerading as option returns, fill queue, assignment or expiry model.

## Architecture and verification

- `src/prizepicks_research`: snapshots/provider mapping, model, orchestration, CLI.
- `src/paper_trading`: validated records, provider adapter, indicators, strategies,
  persistent paper risk ledger, replay, CLI.
- `src/research_common`: strict numbers/timestamps, redacted GET-only transport.
- Existing `agents/` and `player_prop_v2/` remain legacy offline tools unchanged.

Provider contract references: [The Odds API v4](https://the-odds-api.com/liveapi/guides/v4/),
[Alpaca stock data](https://docs.alpaca.markets/reference/stockbars),
[Alpaca options](https://docs.alpaca.markets/reference/optionsnapshots),
and the official [stock](https://github.com/alpacahq/alpaca-py/blob/master/alpaca/data/historical/stock.py)
and [option](https://github.com/alpacahq/alpaca-py/blob/master/alpaca/data/historical/option.py)
SDK implementations. The adapters use the documented `/v2/stocks/bars`,
`/v1beta1/options/snapshots/{underlying}`, and v4 event-odds schemas with
pagination. Contract tests use synthetic recorded response structures; they
establish parser behavior, not live subscription access. No provider secrets
were available during implementation, so authenticated live ingestion was not tested.

Run `python -m unittest discover -s tests -v`. CI installs the package and runs
both new and existing tests. All test prices, lines and identities are synthetic.
