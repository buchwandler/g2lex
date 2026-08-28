"""Slow release gate for the complete German source."""
from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_config
from .run_config import run_config
from .sources import load_source


def run_gate(config_path: str | Path) -> list[dict[str, object]]:
    config = load_config(config_path)
    source = config.values["source"]
    try:
        loaded = load_source(str(source.get("id", "builtin")), data_root=Path(source["data_root"]) if source.get("data_root") else None, path=Path(source["path"]) if source.get("path") else None)
    except (FileNotFoundError, ValueError) as exc:
        raise RuntimeError(f"full-source gate cannot run: exact source is unavailable ({exc})") from exc
    expected = config.values.get("expected_baseline_word_count")
    if expected is None:
        raise RuntimeError("full-source gate requires expected_baseline_word_count in the resolved configuration")
    if len(loaded.entries) != int(expected):
        raise RuntimeError(f"full-source gate baseline count mismatch: expected {expected}, got {len(loaded.entries)}")
    return run_config(config_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args(argv)
    run_gate(args.config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
