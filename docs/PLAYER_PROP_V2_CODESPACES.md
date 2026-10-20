# Codespaces: Player Prop V2
1. Open https://codespaces.new/judson-5/ai and create a Codespace if prompted.
2. In the Codespaces terminal run `python -m unittest discover -s tests -v`.
3. Run `python -m player_prop_v2`. The safe offline sample returns NO QUALIFYING PICKS.
4. To use your authorized datasets, add `data/private/validated_candidates.json` (ignored by git) and run `python -m player_prop_v2 data/private/validated_candidates.json`.
5. Read `player_prop_v2/README.md` for input fields and honest coverage limits.

**Important:** This is a verified-input filter, not a live sports prediction engine. Nothing will place wagers. Preserve the existing paper trading agent.
