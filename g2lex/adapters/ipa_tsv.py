"""Adapter for TSV sources with slash-delimited IPA pronunciations."""

from __future__ import annotations

from pathlib import Path

from ..model import TypedLexiconData
from .common import result

_RECOGNIZED_HEADERS = frozenset({"espeak_ipa", "ipa", "pronunciation"})


def _text(data: bytes, path: Path | None, source_id: str | None) -> tuple[str, str]:
    label = str(path or source_id or "ipa-tsv")
    try:
        return data.decode("utf-8"), label
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label}: invalid UTF-8 IPA TSV: {exc}") from exc


def _strip_outer_delimiters(value: str) -> str:
    value = value.removeprefix("/")
    value = value.removesuffix("/")
    return value


def parse_ipa_tsv_bytes(
    data: bytes,
    *,
    path: Path | None = None,
    source_id: str | None = None,
) -> TypedLexiconData:
    """Parse ``word<TAB>/IPA/`` rows into logical IPA values.

    Only an exact recognized header in the first physical row is skipped. Blank
    rows are ignored. An optional third source annotation field is accepted and
    ignored because this format has no role-specific pronunciation dimension.
    """
    text, label = _text(data, path, source_id)
    values: dict[str, list[str]] = {}
    physical_rows = 0
    for line_number, line in enumerate(text.splitlines(), 1):
        physical_rows += 1
        if not line:
            continue
        fields = line.split("\t")
        if len(fields) not in (2, 3):
            raise ValueError(f"{label}:{line_number}: expected two or three tab-separated fields")
        word, pronunciation = fields[:2]
        if line_number == 1 and word == "word" and pronunciation in _RECOGNIZED_HEADERS:
            continue
        if not word:
            raise ValueError(f"{label}:{line_number}: empty spelling")
        if not pronunciation:
            raise ValueError(f"{label}:{line_number}: empty pronunciation")
        values.setdefault(word, []).append(_strip_outer_delimiters(pronunciation))
    entries = {word: tuple(items) for word, items in values.items()}
    return result(
        entries,
        path=path,
        data=data,
        fmt="ipa-tsv",
        source_id=source_id,
        physical_rows=physical_rows,
    )
