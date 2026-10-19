"""Read supplied CSV history and prices. Offline research; no network or wagering."""
import argparse
import csv
import json
from dataclasses import asdict
from datetime import date
from math import isfinite
from pathlib import Path

from .props import evaluate_prop

HISTORY_FIELDS = ["player", "game_date", "market", "value"]
PROP_FIELDS = ["player", "market", "line", "side", "decimal_odds", "as_of"]


def read_rows(path, fields):
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != fields:
            raise ValueError("Expected CSV headers: " + ",".join(fields))
        rows = list(reader)
    if not rows or any(None in row or any(not value or not value.strip()
                                          for value in row.values()) for row in rows):
        raise ValueError("CSV must contain complete, nonempty rows")
    return rows


def number(value):
    result = float(value)
    if not isfinite(result):
        raise ValueError("Numeric inputs must be finite")
    return result


def build_reports(history_path, props_path):
    history = read_rows(history_path, HISTORY_FIELDS)
    seen = set()
    for row in history:
        row["game_date"] = date.fromisoformat(row["game_date"])
        row["value"] = number(row["value"])
        key = (row["player"], row["market"], row["game_date"])
        if key in seen:
            raise ValueError("Duplicate player/market/date history row")
        seen.add(key)
    reports = []
    for prop in read_rows(props_path, PROP_FIELDS):
        cutoff = date.fromisoformat(prop["as_of"])
        results = [row["value"] for row in history
                   if row["player"] == prop["player"] and row["market"] == prop["market"]
                   and row["game_date"] < cutoff]
        if not results:
            raise ValueError("No matching historical results before as_of date")
        report = evaluate_prop(prop["player"], prop["market"], number(prop["line"]),
                               prop["side"], results, number(prop["decimal_odds"]))
        reports.append({"as_of": prop["as_of"], **asdict(report)})
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", default="data/sample_game_logs.csv")
    parser.add_argument("--props", default="data/sample_props.csv")
    args = parser.parse_args()
    try:
        reports = build_reports(args.history, args.props)
    except (ValueError, OSError) as error:
        parser.exit(2, f"Input error: {error}\n")
    print(json.dumps({"mode": "OFFLINE_RESEARCH_ONLY", "reports": reports}, indent=2,
                     allow_nan=False))


if __name__ == "__main__":
    main()
