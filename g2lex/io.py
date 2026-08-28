"""Strict, language-neutral pronunciation-lexicon I/O."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .model import LexiconData, SourceInfo


class LexiconFormatError(ValueError):
    """Raised when an input lexicon does not match its declared format."""


def _source(path: Path, data: bytes, fmt: str, source_id: str | None = None) -> SourceInfo:
    return SourceInfo(
        source_id=source_id or path.stem,
        sha256=hashlib.sha256(data).hexdigest(),
        format=fmt,
        path=str(path),
        size_bytes=len(data),
    )


def parse_typed_bytes(
    data: bytes,
    *,
    format: str,
    path: Path | None = None,
    source_id: str | None = None,
    allow_tagged: bool = True,
    allow_lists: bool = True,
):
    """Parse a named source format into ``TypedLexiconData``."""
    from .adapters import (
        parse_cmudict_bytes,
        parse_extended_tsv_bytes,
        parse_json_map_bytes,
        parse_jsonl_bytes,
        parse_kokoro_json_bytes,
        parse_mfa_bytes,
        parse_pls_bytes,
        parse_tsv_bytes,
        parse_word_list_bytes,
    )

    if format in {"json", "kokoro-json"}:
        return parse_kokoro_json_bytes(
            data, path=path, source_id=source_id, allow_lists=allow_lists
        )
    if format == "json-map":
        return parse_json_map_bytes(data, path=path, source_id=source_id, allow_tagged=allow_tagged)
    if format == "jsonl":
        return parse_jsonl_bytes(data, path=path, source_id=source_id)
    if format == "cmudict":
        return parse_cmudict_bytes(data, path=path, source_id=source_id)
    if format == "mfa":
        return parse_mfa_bytes(data, path=path, source_id=source_id)
    if format == "pls":
        return parse_pls_bytes(data, path=path, source_id=source_id)
    if format == "tsv":
        return parse_tsv_bytes(data, path=path, source_id=source_id)
    if format == "lxc-tsv":
        return parse_extended_tsv_bytes(data, path=path, source_id=source_id)
    if format == "words":
        return parse_word_list_bytes(data, path=path, source_id=source_id)
    raise ValueError(f"unsupported typed lexicon format: {format!r}")


def read_typed_lexicon(
    path: str | Path,
    *,
    format: str = "auto",
    source_id: str | None = None,
    allow_tagged: bool = True,
    allow_lists: bool = True,
):
    source_path = Path(path)
    fmt = format
    if fmt == "auto":
        suffix = source_path.suffix.lower()
        fmt = {
            ".json": "kokoro-json",
            ".jsonl": "jsonl",
            ".txt": "words",
            ".dict": "cmudict",
            ".mfa": "mfa",
            ".pls": "pls",
            ".xml": "pls",
            ".sqlite": "gruut-sqlite",
            ".db": "gruut-sqlite",
        }.get(suffix, "tsv")
    if fmt == "gruut-sqlite":
        from .adapters import parse_gruut_sqlite

        return parse_gruut_sqlite(source_path, source_id=source_id)
    data = source_path.read_bytes()
    return parse_typed_bytes(
        data,
        format=fmt,
        path=source_path,
        source_id=source_id or source_path.stem,
        allow_tagged=allow_tagged,
        allow_lists=allow_lists,
    )


def parse_json_bytes(
    data: bytes, *, path: Path | None = None, source_id: str = "json"
) -> LexiconData:
    label = str(path or source_id)
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LexiconFormatError(f"{label}: invalid UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise LexiconFormatError(f"{label}: JSON root must be an object")
    entries: dict[str, tuple[str, ...]] = {}
    for word, raw in value.items():
        if not isinstance(word, str) or not word:
            raise LexiconFormatError(f"{label}: JSON keys must be non-empty strings")
        if isinstance(raw, str):
            variants = (raw,)
        elif isinstance(raw, list) and raw and all(isinstance(item, str) for item in raw):
            variants = tuple(raw)
        else:
            raise LexiconFormatError(
                f"{label}: value for {word!r} must be a string or non-empty list of strings"
            )
        entries[word] = variants
    source = (
        _source(path, data, "json", source_id)
        if path is not None
        else SourceInfo(
            source_id, sha256=hashlib.sha256(data).hexdigest(), format="json", size_bytes=len(data)
        )
    )
    return LexiconData(entries, source, len(entries)).runtime_unique()


def parse_tsv_bytes(
    data: bytes, *, path: Path | None = None, source_id: str = "tsv"
) -> LexiconData:
    label = str(path or source_id)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LexiconFormatError(f"{label}: invalid UTF-8 TSV: {exc}") from exc
    entries: dict[str, list[str]] = {}
    rows = 0
    for line_number, line in enumerate(text.splitlines(), 1):
        rows += 1
        fields = line.split("\t")
        if len(fields) != 2:
            raise LexiconFormatError(
                f"{label}:{line_number}: expected 2 tab-separated fields, got {len(fields)}"
            )
        word, pronunciation = fields
        if not word:
            raise LexiconFormatError(f"{label}:{line_number}: empty spelling")
        entries.setdefault(word, []).append(pronunciation)
    source = (
        _source(path, data, "tsv", source_id)
        if path is not None
        else SourceInfo(
            source_id, sha256=hashlib.sha256(data).hexdigest(), format="tsv", size_bytes=len(data)
        )
    )
    return LexiconData(
        {word: tuple(values) for word, values in entries.items()}, source, rows
    ).runtime_unique()


def read_lexicon(
    path: str | Path, *, format: str = "auto", source_id: str | None = None
) -> LexiconData:
    source_path = Path(path)
    data = source_path.read_bytes()
    fmt = format
    if fmt == "auto":
        fmt = "json" if source_path.suffix.lower() == ".json" else "tsv"
    if fmt == "json":
        return parse_json_bytes(data, path=source_path, source_id=source_id or source_path.stem)
    if fmt == "tsv":
        return parse_tsv_bytes(data, path=source_path, source_id=source_id or source_path.stem)
    raise ValueError(f"unsupported lexicon format: {format!r}")


def write_lexicon(path: str | Path, lexicon: LexiconData, *, format: str = "auto") -> None:
    destination = Path(path)
    fmt = format
    if fmt == "auto":
        fmt = "json" if destination.suffix.lower() == ".json" else "tsv"
    if fmt == "json":
        payload: dict[str, object] = {}
        for word, values in lexicon.entries.items():
            payload[word] = values[0] if len(values) == 1 else list(values)
        destination.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return
    if fmt == "tsv":
        lines = [
            f"{word}\t{value}\n" for word in lexicon.words for value in lexicon.lookup_all(word)
        ]
        destination.write_text("".join(lines), encoding="utf-8")
        return
    raise ValueError(f"unsupported lexicon format: {format!r}")
