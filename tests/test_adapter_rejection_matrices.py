"""Focused rejection and fidelity matrices for external adapters."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from g2lex.adapters.cmudict import parse_cmudict_bytes
from g2lex.adapters.gruut_sqlite import parse_gruut_sqlite
from g2lex.adapters.tsv import parse_extended_tsv_bytes, parse_tsv_bytes


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"a\n", "expected two"),
        (b"\tx\n", "empty spelling"),
        (b"a\t\n", "empty pronunciation"),
        (b"\xff", "invalid UTF-8"),
    ],
)
def test_tsv_rejection_matrix(data: bytes, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_tsv_bytes(data, source_id="fixture")


def test_extended_tsv_rejects_unsupported_value_shapes() -> None:
    with pytest.raises(ValueError, match="scalar row"):
        parse_extended_tsv_bytes(b"word\tscalar\t\t1\n")
    with pytest.raises(ValueError, match="list row"):
        parse_extended_tsv_bytes(b"word\tlist\t\t[1]\n")
    with pytest.raises(ValueError, match="multiple rows"):
        parse_extended_tsv_bytes(b"word\tword\t\t\nword\tword\t\t\n")


def test_cmudict_comments_empty_values_and_variant_fidelity() -> None:
    parsed = parse_cmudict_bytes(b"WORD(2) W ER D\nWORD W AH R D\nWORD(foo) F OO\n")

    assert parsed.entries["WORD"] == ("W ER D", "W AH R D")
    assert parsed.entries["WORD(foo)"] == ("F OO",)
    with pytest.raises(ValueError, match="expected WORD"):
        parse_cmudict_bytes(b"WORD\n")
    with pytest.raises(ValueError, match="expected WORD"):
        parse_cmudict_bytes(b"WORD \n")


def _database(path: Path, schema: str | None = None) -> None:
    with sqlite3.connect(path) as connection:
        if schema is not None:
            connection.execute(schema)


def test_gruut_rejects_missing_table_and_malformed_fields(tmp_path: Path) -> None:
    missing = tmp_path / "missing.sqlite"
    _database(missing)
    with pytest.raises(ValueError, match="needs word_phonemes"):
        parse_gruut_sqlite(missing)

    malformed = tmp_path / "malformed.sqlite"
    _database(malformed, "CREATE TABLE word_phonemes (word TEXT, pron_order INTEGER, phonemes BLOB)")
    with sqlite3.connect(malformed) as connection:
        connection.execute("INSERT INTO word_phonemes VALUES (?, ?, ?)", ("word", 1, None))
    with pytest.raises(TypeError, match="phonemes must be strings"):
        parse_gruut_sqlite(malformed)


def test_gruut_rejects_mixed_tagged_and_untagged_values(tmp_path: Path) -> None:
    path = tmp_path / "mixed.sqlite"
    _database(
        path,
        "CREATE TABLE word_phonemes (word TEXT, pron_order INTEGER, phonemes TEXT, role TEXT)",
    )
    with sqlite3.connect(path) as connection:
        connection.executemany(
            "INSERT INTO word_phonemes VALUES (?, ?, ?, ?)",
            [("word", 1, "w", None), ("word", 2, "w", "noun")],
        )
    with pytest.raises(ValueError, match="mixes tagged"):
        parse_gruut_sqlite(path)
