"""Adapter for Kokoro pronunciation JSON files."""

from __future__ import annotations

import json
from pathlib import Path

from ..model import TypedLexiconData
from .common import parse_value, result


def parse_kokoro_json_bytes(
    data: bytes,
    *,
    path: Path | None = None,
    source_id: str | None = None,
    allow_lists: bool = True,
) -> TypedLexiconData:
    label = str(path or source_id or "kokoro-json")
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
        if isinstance(raw, list) and not allow_lists:
            raise ValueError(f"{label}: lists are disabled for {word!r}")
        try:
            entries[word] = parse_value(raw, f"{label}:{word}")
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
    return result(
        entries,
        path=path,
        data=data,
        fmt="kokoro-json",
        source_id=source_id,
        physical_rows=len(entries),
    )
