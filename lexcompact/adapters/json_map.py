"""Adapter for generic JSON maps."""

from __future__ import annotations

import json
from pathlib import Path

from ..model import TypedLexiconData
from .common import parse_value, result


def parse_json_map_bytes(
    data: bytes,
    *,
    path: Path | None = None,
    source_id: str | None = None,
    allow_tagged: bool = True,
) -> TypedLexiconData:
    label = str(path or source_id or "json-map")
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label}: invalid UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise TypeError(f"{label}: JSON root must be an object")
    entries = {}
    for word, raw in value.items():
        if not isinstance(word, str) or not word:
            raise ValueError(f"{label}: keys must be non-empty strings")
        if isinstance(raw, dict) and not allow_tagged:
            raise ValueError(f"{label}: tagged values are disabled for {word!r}")
        entries[word] = parse_value(raw, f"{label}:{word}")
    return result(
        entries,
        path=path,
        data=data,
        fmt="json-map",
        source_id=source_id,
        physical_rows=len(entries),
    )
