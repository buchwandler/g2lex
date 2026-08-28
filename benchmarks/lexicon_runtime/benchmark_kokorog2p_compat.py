"""Exercise virtual alias and raw G2Lex v1 lookup paths."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from g2lex import CaseAliasMapping, open


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("asset", type=Path)
    parser.add_argument("words", nargs="+")
    args = parser.parse_args()
    raw = open(args.asset)
    mapping = CaseAliasMapping(raw)
    try:
        started = time.perf_counter()
        hits = sum(mapping.get(word) is not None for word in args.words)
        elapsed = time.perf_counter() - started
        print(json.dumps({"lookups": len(args.words), "hits": hits, "seconds": elapsed}, indent=2))
    finally:
        raw.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
