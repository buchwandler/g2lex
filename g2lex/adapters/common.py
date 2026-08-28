"""Shared validation for typed source adapters."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..model import SourceInfo, TypedLexiconData
from ..value import LexiconValue, TaggedValue


def source_info(path: Path | None, data: bytes, fmt: str, source_id: str | None) -> SourceInfo:
    return SourceInfo(
        source_id=source_id or (path.stem if path else fmt),
        sha256=hashlib.sha256(data).hexdigest(),
        format=fmt,
        path=str(path) if path else None,
        size_bytes=len(data),
    )


def result(
    entries: Mapping[str, LexiconValue],
    *,
    path: Path | None,
    data: bytes,
    fmt: str,
    source_id: str | None,
    physical_rows: int,
) -> TypedLexiconData:
    return TypedLexiconData(
        dict(entries),
        source=source_info(path, data, fmt, source_id),
        physical_rows=physical_rows,
    )


def parse_selector_value(value: Any, label: str) -> str | None | tuple[str, ...]:
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return tuple(value)
    raise ValueError(f"{label}: selector value must be a string, null, or list of strings")


def parse_value(value: Any, label: str, *, allow_word: bool = False) -> LexiconValue:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return tuple(value)
    if isinstance(value, dict):
        return TaggedValue(
            tuple(
                (tag, parse_selector_value(item, f"{label}.{tag}")) for tag, item in value.items()
            )
        )
    if allow_word and value is None:
        from ..value import WORD_ONLY

        return WORD_ONLY
    raise ValueError(f"{label}: expected string, list of strings, or selector object")
