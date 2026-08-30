"""Stable JSON and TSV output for lexicon-analysis runs."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from g2lex.value import WORD_ONLY, TaggedValue


def jsonable(value: object) -> object:
    if value is WORD_ONLY:
        return "WORD_ONLY"
    if isinstance(value, TaggedValue):
        return {tag: jsonable(selector) for tag, selector in value.items}
    if isinstance(value, tuple):
        return [jsonable(item) for item in value]
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(jsonable(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_tsv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    materialized = [{key: jsonable(value) for key, value in row.items()} for row in rows]
    fields = sorted({key for row in materialized for key in row})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="ignore"
        )
        if fields:
            writer.writeheader()
            writer.writerows(materialized)


def write_run(output: Path, summary: Mapping[str, object]) -> None:
    """Write the documented machine-readable summary and convenience tables."""
    write_json(output / "summary.json", summary)
    sources = summary.get("sources", [])
    pairs = summary.get("pairs", [])
    layers = summary.get("layers", {})
    write_tsv(output / "sources.tsv", sources if isinstance(sources, list) else [])
    write_tsv(output / "pairs.tsv", pairs if isinstance(pairs, list) else [])
    write_tsv(
        output / "conflicts.tsv",
        [
            {"source_a": pair.get("source_a"), "source_b": pair.get("source_b"), **conflict}
            for pair in pairs
            if isinstance(pair, Mapping)
            for conflict in pair.get("conflicts", [])
            if isinstance(conflict, Mapping)
        ],
    )
    write_tsv(
        output / "collisions.tsv",
        [
            {
                "source": source.get("source"),
                "key_type": key,
                "key": collision_key,
                "spellings": values,
            }
            for source in sources
            if isinstance(source, Mapping)
            for key, groups in source.get("keys", {}).items()
            if key.endswith("_collisions")
            for collision_key, values in groups.items()
        ],
    )
    write_tsv(
        output / "unicode.tsv",
        [
            {"source": source.get("source"), **source.get("unicode", {})}
            for source in sources
            if isinstance(source, Mapping)
        ],
    )
    layer_rows = layers.get("rows", []) if isinstance(layers, Mapping) else []
    write_tsv(output / "layers.tsv", layer_rows if isinstance(layer_rows, list) else [])


__all__ = ["jsonable", "write_json", "write_run", "write_tsv"]
