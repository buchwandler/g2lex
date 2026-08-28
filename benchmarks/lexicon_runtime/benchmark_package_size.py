"""Report source and V5 package sizes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("asset", type=Path)
    args = parser.parse_args()
    source_size = args.source.stat().st_size
    asset_size = args.asset.stat().st_size
    print(json.dumps({"source_bytes": source_size, "asset_bytes": asset_size, "ratio": asset_size / source_size}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
