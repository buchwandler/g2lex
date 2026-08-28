"""Create and validate immutable source records for benchmark inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .sources import MANIFEST_PATH, load_manifest, load_source

EXPECTED_REPOSITORY_COMMIT = "2e1b9ffdefda094102d1caee4e1fceff955e8956"


def build_lock(
    path: str | Path,
    *,
    source_id: str = "builtin",
    expected_words: int | None = None,
    kokorog2p_version: str | None = None,
    repository_commit: str | None = EXPECTED_REPOSITORY_COMMIT,
    manifest_path: Path = MANIFEST_PATH,
) -> dict[str, Any]:
    source_path = Path(path).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    manifest = load_manifest(manifest_path)
    if source_id not in manifest:
        raise ValueError(f"unknown source id: {source_id}")
    raw = source_path.read_bytes()
    parsed = load_source(source_id, path=source_path, manifest_path=manifest_path)
    logical_words = len(parsed.entries)
    if expected_words is not None and logical_words != expected_words:
        raise ValueError(f"expected {expected_words} logical words, got {logical_words}")
    spec = manifest[source_id]
    return {
        "source_id": source_id,
        "kokorog2p_version": kokorog2p_version,
        "repository_commit": repository_commit,
        "git_blob_sha": None,
        "path": source_path.name,
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "logical_word_count": logical_words,
        "ordered_variant_count": parsed.variant_count,
        "parser_version": spec.parser_version,
        "view_version": spec.view_version,
        "format": parsed.source.format,
    }


def validate_lock(
    lock: dict[str, Any],
    *,
    path: str | Path,
    source_id: str | None = None,
    expected_words: int | None = None,
    repository_commit: str = EXPECTED_REPOSITORY_COMMIT,
    manifest_path: Path = MANIFEST_PATH,
) -> dict[str, Any]:
    actual = build_lock(
        path,
        source_id=str(source_id or lock.get("source_id", "builtin")),
        expected_words=expected_words,
        kokorog2p_version=lock.get("kokorog2p_version"),
        repository_commit=repository_commit,
        manifest_path=manifest_path,
    )
    checks = {
        "sha256": actual["sha256"] == lock.get("sha256"),
        "size_bytes": actual["size_bytes"] == lock.get("size_bytes"),
        "logical_word_count": actual["logical_word_count"] == lock.get("logical_word_count"),
        "ordered_variant_count": actual["ordered_variant_count"]
        == lock.get("ordered_variant_count"),
        "parser_version": actual["parser_version"] == lock.get("parser_version"),
        "view_version": actual["view_version"] == lock.get("view_version"),
        "repository_commit": lock.get("repository_commit") == repository_commit,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError("source lock mismatch: " + ", ".join(failed))
    return actual


def load_lock(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("source lock must be a JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--source-id", default="builtin")
    parser.add_argument("--expected-words", type=int)
    parser.add_argument("--kokorog2p-version")
    parser.add_argument("--repository-commit", default=EXPECTED_REPOSITORY_COMMIT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    lock = build_lock(
        args.path,
        source_id=args.source_id,
        expected_words=args.expected_words,
        kokorog2p_version=args.kokorog2p_version,
        repository_commit=args.repository_commit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(lock, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(lock, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
