"""Report basic lazy-runtime memory proxies without optional dependencies."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lexcompact import open_lexicon


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("asset", type=Path)
    args = parser.parse_args()
    before = sys.getallocatedblocks() if hasattr(sys, "getallocatedblocks") else None
    lexicon = open_lexicon(args.asset)
    after_open = sys.getallocatedblocks() if before is not None else None
    try:
        for word in lexicon:
            lexicon.get(word)
        after_iteration = sys.getallocatedblocks() if before is not None else None
        print(json.dumps({"entries": len(lexicon), "allocated_blocks_open_delta": None if before is None else after_open - before, "allocated_blocks_iteration_delta": None if after_open is None else after_iteration - after_open}, indent=2))
    finally:
        lexicon.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
