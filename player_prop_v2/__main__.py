"""Run: python -m player_prop_v2 [file.json]"""
import json
import sys
from .scanner import scan_file
from pathlib import Path

def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("player_prop_v2/sample.json")
    print(json.dumps(scan_file(src), indent=2, default=str))

if __name__ == "__main__":
    main()
