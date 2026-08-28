"""Legacy two-column and canonical extended TSV adapters."""

from __future__ import annotations

import json
from pathlib import Path

from ..model import TypedLexiconData
from ..value import WORD_ONLY, TaggedValue
from .common import parse_selector_value, result


def _text(data: bytes, path: Path | None, source_id: str | None, fmt: str) -> tuple[str, str]:
    label = str(path or source_id or fmt)
    try:
        return data.decode("utf-8"), label
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label}: invalid UTF-8 TSV: {exc}") from exc


def parse_tsv_bytes(
    data: bytes,
    *,
    path: Path | None = None,
    source_id: str | None = None,
) -> TypedLexiconData:
    text, label = _text(data, path, source_id, "tsv")
    values: dict[str, list[str]] = {}
    rows = 0
    for line_number, line in enumerate(text.splitlines(), 1):
        rows += 1
        fields = line.split("\t")
        if len(fields) != 2:
            raise ValueError(f"{label}:{line_number}: expected two tab-separated fields")
        word, pronunciation = fields
        if not word:
            raise ValueError(f"{label}:{line_number}: empty spelling")
        values.setdefault(word, []).append(pronunciation)
    entries = {word: tuple(items) for word, items in values.items()}
    return result(entries, path=path, data=data, fmt="tsv", source_id=source_id, physical_rows=rows)


def parse_extended_tsv_bytes(
    data: bytes,
    *,
    path: Path | None = None,
    source_id: str | None = None,
) -> TypedLexiconData:
    text, label = _text(data, path, source_id, "lxc-tsv")
    rows = 0
    grouped: dict[str, list[tuple[str, object]]] = {}
    for line_number, line in enumerate(text.splitlines(), 1):
        rows += 1
        fields = line.split("\t")
        if len(fields) != 4:
            raise ValueError(f"{label}:{line_number}: expected four tab-separated fields")
        word, kind, selector, encoded = fields
        if not word:
            raise ValueError(f"{label}:{line_number}: empty spelling")
        try:
            value = json.loads(encoded) if encoded else None
        except json.JSONDecodeError as exc:
            raise ValueError(f"{label}:{line_number}: invalid value JSON: {exc}") from exc
        if kind == "tagged":
            if not selector:
                raise ValueError(f"{label}:{line_number}: tagged row needs a selector")
            selector_value = parse_selector_value(value, f"{label}:{line_number}")
            grouped.setdefault(word, []).append((selector, selector_value))
        elif kind == "scalar":
            if selector or not isinstance(value, str):
                raise ValueError(
                    f"{label}:{line_number}: scalar row needs an empty selector and string value"
                )
            grouped.setdefault(word, []).append(("", value))
        elif kind == "list":
            if (
                selector
                or not isinstance(value, list)
                or not all(isinstance(item, str) for item in value)
            ):
                raise ValueError(
                    f"{label}:{line_number}: list row needs an empty selector and string list"
                )
            grouped.setdefault(word, []).append(("__list__", tuple(value)))
        elif kind == "word":
            if selector or encoded:
                raise ValueError(f"{label}:{line_number}: word row has unexpected data")
            grouped.setdefault(word, []).append(("__word__", WORD_ONLY))
        else:
            raise ValueError(f"{label}:{line_number}: unsupported kind {kind!r}")
    entries = {}
    for word, rows_for_word in grouped.items():
        kinds = {marker for marker, _ in rows_for_word}
        if "__word__" in kinds:
            if len(rows_for_word) != 1:
                raise ValueError(f"{label}: word-only entry {word!r} has multiple rows")
            entries[word] = WORD_ONLY
        elif "__list__" in kinds:
            if len(rows_for_word) != 1:
                raise ValueError(f"{label}: list entry {word!r} has multiple rows")
            entries[word] = rows_for_word[0][1]
        elif "" in kinds:
            values = [value for marker, value in rows_for_word if marker == ""]
            entries[word] = values[0] if len(values) == 1 else tuple(values)
        else:
            entries[word] = TaggedValue(tuple(rows_for_word))
    return result(
        entries, path=path, data=data, fmt="lxc-tsv", source_id=source_id, physical_rows=rows
    )
