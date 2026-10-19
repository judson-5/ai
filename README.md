# AI Research & Paper Trading Agents

Two independent Python research modules. **No live order or wagering API is implemented.** This public repository contains no secrets.

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
