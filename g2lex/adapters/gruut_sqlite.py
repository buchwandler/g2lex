"""Gruut-style pronunciation lexicon SQLite adapter."""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path

from ..model import SourceInfo, TypedLexiconData
from ..value import TaggedValue


def parse_gruut_sqlite(path: str | Path, *, source_id: str | None = None) -> TypedLexiconData:
    """Import the ``word_phonemes`` table without depending on Gruut."""
    source_path = Path(path)
    data = source_path.read_bytes()
    with closing(sqlite3.connect(f"file:{source_path.resolve()}?mode=ro", uri=True)) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(word_phonemes)")}
        required = {"word", "pron_order", "phonemes"}
        if not required.issubset(columns):
            raise ValueError(
                "Gruut SQLite database needs word_phonemes(word, pron_order, phonemes)"
            )
        role_expression = "role" if "role" in columns else "NULL"
        rows = connection.execute(
            f"SELECT word, pron_order, phonemes, {role_expression} "
            "FROM word_phonemes ORDER BY word, pron_order, rowid"
        )
        grouped: dict[str, dict[str | None, list[str]]] = {}
        physical_rows = 0
        for word, _pron_order, phonemes, role in rows:
            if not isinstance(word, str) or not word:
                raise ValueError("Gruut SQLite word values must be non-empty strings")
            if not isinstance(phonemes, str):
                raise TypeError("Gruut SQLite phonemes must be strings")
            grouped.setdefault(word, {}).setdefault(role, []).append(phonemes)
            physical_rows += 1

    entries = {}
    for word, by_role in grouped.items():
        if set(by_role) == {None}:
            values = by_role[None]
            entries[word] = values[0] if len(values) == 1 else tuple(values)
            continue
        if None in by_role:
            raise ValueError("Gruut SQLite record mixes tagged and untagged pronunciations")
        entries[word] = TaggedValue(
            tuple(
                (role, values[0] if len(values) == 1 else tuple(values))
                for role, values in by_role.items()
            )
        )
    source = SourceInfo(
        source_id=source_id or source_path.stem,
        provider="gruut",
        source_format="gruut-sqlite",
        format="gruut-sqlite",
        path=str(source_path),
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )
    return TypedLexiconData(entries, source=source, physical_rows=physical_rows)
