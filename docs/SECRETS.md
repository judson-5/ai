# Secrets and data access

The installed research tools run offline and require no key. There is no Odds API adapter, credential validation request, sportsbook integration, or automatic wagering.

If you later add an authorized read-only Odds API adapter:

1. Open https://github.com/settings/codespaces and create a Codespaces secret named `ODDS_API_KEY`.
2. Grant repository access only to `judson-5/ai`. Paste the credential directly into GitHub's secret field.
3. Restart an existing codespace so it receives the secret.
4. Application code should read `os.environ.get("ODDS_API_KEY")`. Never print it or include it in exception messages, request URLs in logs, source, CSV files, reports, screenshots, or chat.

An Actions secret does not automatically become a Codespaces secret. The connector used for this installation cannot create or inspect account secrets. Do not send the key to the assistant. No key was requested, invented, or added by this installation.

Python does not automatically load `.env` files. Use environment injection; `.env.example` is documentation only. Local `.env` files and private datasets must remain untracked. Use `data/private/` for your own CSVs. Git ignore rules cannot remove files already committed. If a credential is ever committed, revoke/rotate it immediately and clean repository history as needed.
