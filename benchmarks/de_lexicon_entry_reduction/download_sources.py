#!/usr/bin/env python3
"""Explicitly download pinned German benchmark sources."""

from __future__ import annotations

import argparse
from pathlib import Path

from .download import download_source
from .sources import load_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Comma-separated source IDs")
    parser.add_argument("--download", action="store_true", help="Required explicit network opt-in")
    parser.add_argument("--cache-dir", type=Path)
    args = parser.parse_args(argv)
    if not args.download:
        parser.error("refusing network access: pass --download explicitly")
    specs = load_manifest()
    for source_id in (item.strip() for item in args.source.split(",")):
        if source_id == "builtin":
            print("builtin is packaged by kokorog2p; no download required")
            continue
        try:
            path = download_source(specs[source_id], cache_dir=args.cache_dir)
        except (KeyError, OSError, ValueError) as exc:
            parser.error(str(exc))
        print(f"{source_id}\t{path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
