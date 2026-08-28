"""Measure cold and warm V5 lookups."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from lexcompact import open_lexicon


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("asset", type=Path)
    parser.add_argument("words", nargs="+")
    args = parser.parse_args()
    lexicon = open_lexicon(args.asset)
    try:
        started = time.perf_counter()
        for word in args.words:
            lexicon.get(word)
        cold = time.perf_counter() - started
        started = time.perf_counter()
        for word in args.words:
            lexicon.get(word)
        warm = time.perf_counter() - started
        print(json.dumps({"lookups": len(args.words), "cold_seconds": cold, "warm_seconds": warm}, indent=2))
    finally:
        lexicon.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
