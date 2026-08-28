"""Compare JSON parsing and G2Lex v1 opening for a supplied source and asset."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from g2lex import open, read_typed_lexicon


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("asset", type=Path)
    parser.add_argument("--format", default="auto")
    args = parser.parse_args()
    started = time.perf_counter()
    source = read_typed_lexicon(args.source, format=args.format)
    json_time = time.perf_counter() - started
    started = time.perf_counter()
    lexicon = open(args.asset)
    lxc_time = time.perf_counter() - started
    try:
        result = {
            "source_entries": len(source),
            "json_parse_seconds": json_time,
            "lxc_open_seconds": lxc_time,
        }
        print(json.dumps(result, indent=2))
    finally:
        lexicon.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
