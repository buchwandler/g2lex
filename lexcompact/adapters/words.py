"""Adapter for exact membership word lists."""

from __future__ import annotations

from pathlib import Path

from ..model import TypedLexiconData
from ..value import WORD_ONLY
from .common import result


def parse_word_list_bytes(
    data: bytes,
    *,
    path: Path | None = None,
    source_id: str | None = None,
) -> TypedLexiconData:
    label = str(path or source_id or "words")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label}: invalid UTF-8 word list: {exc}") from exc
    entries = {}
    rows = 0
    for line_number, word in enumerate(text.splitlines(), 1):
        rows += 1
        if not word:
            raise ValueError(f"{label}:{line_number}: empty word")
        if word in entries:
            raise ValueError(f"{label}:{line_number}: duplicate word {word!r}")
        entries[word] = WORD_ONLY
    return result(
        entries, path=path, data=data, fmt="words", source_id=source_id, physical_rows=rows
    )
