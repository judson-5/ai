# Secrets and data access

Legacy tools and all offline tests require no keys. The new `src/` applications
include read-only The Odds API and Alpaca market-data adapters. No live-order or
wager-submission integration exists.

For the read-only data adapters:

1. Open https://github.com/settings/codespaces and create `ODDS_API_KEY` for sportsbook data, and `ALPACA_API_KEY` plus `ALPACA_SECRET_KEY` for Alpaca market data. Use separate least-privilege/research credentials where supported. OPRA/SIP feeds require appropriate provider entitlements.
2. Grant repository access only to `judson-5/ai`. Paste the credential directly into GitHub's secret field.
3. Restart an existing codespace so it receives the secret.
4. Application code reads environment variables only. Never print keys or include them in exception messages, request URLs in logs, source, CSV files, reports, screenshots, or chat. The Odds API authenticates in the query string; transport errors deliberately redact URLs. Redirects are disabled to prevent forwarding credentials to another host.

An Actions secret does not automatically become a Codespaces secret. The connector used for this installation cannot create or inspect account secrets. Do not send the key to the assistant. No key was requested, invented, or added by this installation.

Python does not automatically load `.env` files. Use environment injection; `.env.example` is documentation only. Local `.env` files and private datasets must remain untracked. Use `data/private/` for your own CSVs. Git ignore rules cannot remove files already committed. If a credential is ever committed, revoke/rotate it immediately and clean repository history as needed.
