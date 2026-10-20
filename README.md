# AI Research & Paper Trading Agents

Two independent Python research modules. **No live order or wagering API is implemented.** This public repository contains no secrets.

## New research applications

The modular applications in `src/` add current-data intake, explicit evidence
validation, options selection, persistent paper risk management and quote replay:

- **PrizePicks:** `python -m prizepicks_research <snapshot.json>`; accepts
  authorized current PrizePicks snapshots, optionally refreshes two originating
  sportsbooks through The Odds API, excludes promotions/boosts, and requires
  at least 65% modeled hit probability. Missing evidence blocks recommendations.
- **SPY/QQQ:** `python -m paper_trading analyze SPY`; Alpaca read-only market
  data, EMA9/21, session VWAP, momentum and volume, long calls/puts or defined-risk
  credit spreads, SQLite paper ledger, and actual-option-quote replay backtests.

Install first with `python -m pip install -e .`, then run
`python -m unittest discover -s tests -v`. There are no third-party runtime
dependencies. Provider calls require environment credentials and subscriptions.

See the **[installation, iPhone Codespaces operating guide, data contracts and
limitations](docs/RESEARCH_AGENTS.md)** and [secret configuration](docs/SECRETS.md).
The prop model is a conservative uncalibrated research heuristic. PrizePicks
entry EV remains unavailable without actual joint outcomes and payout rules;
sportsbook reference EV is labeled separately. Live authenticated provider calls
have not been tested without credentials.

The original `agents/` and `player_prop_v2/` code remains unchanged. The sections
below describe those legacy offline tools, not the new applications.

## Quick start
Python 3.11+:
```bash
python -m unittest discover -s tests -v
python -m agents.demo
```
All inputs in the demo are synthetic and **not live market prices or sportsbook lines**.

## Components
- `agents/props.py`: historical prop hit rates, conservative probability estimation, decimal-odds break-even, EV and minimum-edge screening. Projections and probabilities are exploratory, not calibrated forecasts.
- `agents/trading.py`: rolling EMA(9/21), intraday VWAP, signal filter, defined-risk spread calculations, capped paper-risk engine and in-memory paper fills.

## Safety and limits
- Trading is **paper-only**; no brokerage integration or live-order path exists.
- No sportsbook, payment or bet-placement integration.
- Input data must be independently sourced and timestamped before making decisions. Do not confuse mock data with current quotes.
- Options are risky. Historical hit frequency does not guarantee future results.
- For production research, add licensed market/sports data ingestion, data-quality validation, fees/slippage, realistic backtests, observability, and calibration before trusting outputs.

## Next steps
Configure authorized read-only data providers, then extend adapters without modifying the paper-only execution boundary. CI runs the unit tests on commits and pull requests.

## iPhone Codespaces setup

Open https://github.com/judson-5/ai in Safari, then **Code > Codespaces > Create codespace on main**. Use **Request Desktop Website** if the controls are hidden. GitHub account eligibility, capacity, and billing prompts are managed by GitHub. This configuration does not create a codespace or accept paid usage on your behalf.

The development container includes Python 3.12, installs the project, and runs the test suite on creation. No third-party runtime packages are required. In the Codespaces terminal run:

```sh
python -m unittest discover -s tests -v
python -m agents.csv_report
python -m agents.demo
```

The CSV command prints a JSON research report from fictional sample data. `qualifies` is a historical screening flag, not a recommendation or an instruction to place a bet. No ZIP download is needed.

## Your CSV data

Copy the header-only files from `data/templates/` into `data/private/` and add your independently sourced data. The private directory is ignored by Git. Run:

```sh
python -m agents.csv_report --history data/private/game_logs.csv --props data/private/props.csv
```

- History headers: `player,game_date,market,value`. Use ISO dates (`YYYY-MM-DD`), finite numeric values, and one row per player/market/date.
- Prop headers: `player,market,line,side,decimal_odds,as_of`. Use `over` or `under` and decimal odds greater than 1. Match player and market names exactly.
- Only games strictly before `as_of` enter the report. Dates do not establish when prices were actually collected; verify freshness yourself.
- Missing matching history, duplicate history rows, incomplete rows, malformed headers, and nonfinite numbers are rejected.
- The original estimator uses smoothed historical win frequency. It does not model opponent, injury, lineup, or market changes. Ties are counted as non-wins in its probability/EV calculation; refundable pushes are not priced separately. Use half-point lines for this demo or interpret integer-line outputs with that limitation.

## Keys and provenance

See [secure secrets instructions](docs/SECRETS.md). Offline tests and legacy examples need no keys; the new applications include read-only provider adapters.

Installation preserves the source already present in `judson-5/ai` at commit `171b9b10f0d6882573b52bdca4b38f7325ec0f6c` and adds a CSV interface, templates, Codespaces configuration, and documentation. The paper demo now uses a spread within its simulated risk cap. The earlier ChatGPT conversation exposed only unresolved content references and no downloadable attachments, so its original ZIP could not be retrieved or compared. This is not a verified restoration of that missing archive.

