"""Build deterministic V5 assets from a JSON build manifest.

The manifest is a JSON array of objects with ``source``, ``asset``, and optional
``format`` and ``metadata`` fields. Source hashes are recorded in the generated
summary, making the build independent of the published wheel.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from lexcompact import pack_file


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path, help="JSON build manifest")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    records = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise TypeError("build manifest must be a JSON array")
    assets = []
    for record in records:
        if not isinstance(record, dict):
            raise TypeError("each build manifest record must be an object")
        source = Path(record["source"])
        output = Path(record["asset"])
        summary = pack_file(
            source,
            output,
            input_format=str(record.get("format", "auto")),
            source_id=record.get("source_id"),
            metadata=record.get("metadata"),
        )
        assets.append({
            "name": record.get("name", output.stem),
            "source": str(source),
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "asset": str(output),
            "asset_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "entries": summary["asset_entry_count"],
        })
    report = {"assets": assets}
    destination = args.report or args.manifest.with_name("lexcompact-assets.json")
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
