"""Slow release gate for the complete, source-locked German lexicon."""

from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_config
from .lock_source import EXPECTED_REPOSITORY_COMMIT, load_lock, validate_lock
from .run_config import run_config
from .sources import load_source


def _path(value: str | None, *, base: Path) -> Path | None:
    if not value:
        return None
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    if candidate.exists():
        return candidate
    return base / candidate


def run_gate(config_path: str | Path) -> list[dict[str, object]]:
    config_file = Path(config_path).resolve()
    config = load_config(config_file)
    values = config.values
    source = values["source"]
    lock_value = values.get("source_lock")
    if not lock_value:
        raise RuntimeError("full-source gate requires source_lock in the resolved configuration")
    lock_path = _path(str(lock_value), base=config_file.parent)
    assert lock_path is not None
    if not lock_path.is_file():
        raise RuntimeError(f"full-source gate source lock is unavailable: {lock_path}")
    lock = load_lock(lock_path)
    source_path = _path(source.get("path"), base=config_file.parent)
    data_root = _path(source.get("data_root"), base=config_file.parent)
    try:
        loaded = load_source(
            str(source.get("id", "builtin")),
            data_root=data_root,
            path=source_path,
        )
        validate_lock(
            lock,
            path=loaded.source.path or source_path or "",
            source_id=str(source.get("id", "builtin")),
            expected_words=int(values.get("expected_baseline_word_count", 738427)),
        )
    except (FileNotFoundError, ValueError) as exc:
        raise RuntimeError(f"full-source gate cannot validate the exact source ({exc})") from exc
    expected = int(values.get("expected_baseline_word_count", 738427))
    if len(loaded.entries) != expected:
        raise RuntimeError(
            f"full-source gate baseline count mismatch: expected {expected}, got {len(loaded.entries)}"
        )
    if lock.get("repository_commit") != EXPECTED_REPOSITORY_COMMIT:
        raise RuntimeError("full-source gate requires the pinned KokoroG2P repository commit")
    return run_config(config_file)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args(argv)
    run_gate(args.config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
