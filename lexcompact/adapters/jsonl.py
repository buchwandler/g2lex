"""Canonical JSONL adapter for typed lexicon interchange."""

from __future__ import annotations

import json
from pathlib import Path

from ..model import TypedLexiconData
from ..value import WORD_ONLY, TaggedValue
from .common import parse_selector_value, parse_value, result


def parse_jsonl_bytes(
    data: bytes,
    *,
    path: Path | None = None,
    source_id: str | None = None,
) -> TypedLexiconData:
    label = str(path or source_id or "jsonl")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label}: invalid UTF-8 JSONL: {exc}") from exc
    entries = {}
    rows = 0
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        rows += 1
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{label}:{line_number}: invalid JSON: {exc}") from exc
        if (
            not isinstance(record, dict)
            or not isinstance(record.get("word"), str)
            or not record["word"]
        ):
            raise ValueError(f"{label}:{line_number}: record needs a non-empty word")
        word = record["word"]
        if word in entries:
            raise ValueError(f"{label}:{line_number}: duplicate word {word!r}")
        kind = record.get("kind")
        if kind == "word":
            value = WORD_ONLY
        elif kind == "scalar":
            if not isinstance(record.get("value"), str):
                raise ValueError(f"{label}:{line_number}: scalar value must be a string")
            value = record["value"]
        elif kind == "list":
            value = parse_value(record.get("value"), f"{label}:{line_number}")
            if not isinstance(value, tuple):
                raise ValueError(f"{label}:{line_number}: list value must be a string list")
        elif kind == "tagged":
            items = record.get("items")
            if not isinstance(items, list):
                raise ValueError(f"{label}:{line_number}: tagged items must be a list")
            pairs = []
            for pair in items:
                if not isinstance(pair, list) or len(pair) != 2 or not isinstance(pair[0], str):
                    raise ValueError(f"{label}:{line_number}: invalid tagged item")
                pairs.append((pair[0], parse_selector_value(pair[1], f"{label}:{line_number}")))
            value = TaggedValue(tuple(pairs))
        else:
            raise ValueError(f"{label}:{line_number}: unsupported record kind {kind!r}")
        entries[word] = value
    return result(
        entries, path=path, data=data, fmt="jsonl", source_id=source_id, physical_rows=rows
    )
