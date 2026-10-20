import argparse
import json
from research_common.http import DataUnavailable
from .adapters import read_snapshot, OddsApi
from .service import scan


def main():
    parser = argparse.ArgumentParser(description="Research authorized PrizePicks snapshots; never place wagers")
    parser.add_argument("snapshot", help="Authorized current JSON snapshot")
    parser.add_argument("--refresh-books", action="store_true", help="GET event props from The Odds API")
    args = parser.parse_args()
    try:
        candidates = read_snapshot(args.snapshot)
        if args.refresh_books:
            provider = OddsApi()
            for candidate in candidates:
                # Do not let a failed refresh leave old supplied books in use.
                candidate["books"] = []
                try:
                    candidate["books"] = provider.books(candidate)
                except (DataUnavailable, KeyError, TypeError, ValueError):
                    candidate["books"] = []
        print(json.dumps(scan(candidates), indent=2, allow_nan=False))
    except (OSError, ValueError, TypeError, DataUnavailable) as error:
        parser.exit(2, f"Research unavailable: {error}\n")


if __name__ == "__main__":
    main()
