from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from g2lex import (
    TypedLexiconData,
    export_file,
    open_bytes,
    pack_file,
    read_typed_lexicon,
    verify_file,
)
from g2lex.adapters import parse_cmudict_bytes, parse_gruut_sqlite, parse_mfa_bytes, parse_pls_bytes
from g2lex.format import pack_typed


def test_cmudict_groups_numbered_variants_in_input_order() -> None:
    source = parse_cmudict_bytes(b";;; comment\nWORD(2) W ER D\nWORD W AH R D\nOTHER OW T ER\n")
    assert source.entries == {"WORD": ("W ER D", "W AH R D"), "OTHER": ("OW T ER",)}
    assert source.source.format == "cmudict"


def test_cmudict_comment_policy_is_explicit() -> None:
    with pytest.raises(ValueError, match="comments are not allowed"):
        parse_cmudict_bytes(b";;; header\nWORD W ER D\n", comment_policy="error")


def test_mfa_preserves_repeated_variants_and_rejects_probabilities() -> None:
    source = parse_mfa_bytes(b"word\tw er d\nword\tw <sil> d\n")
    assert source.entries["word"] == ("w er d", "w <sil> d")
    with pytest.raises(ValueError, match="probabilistic MFA dictionaries"):
        parse_mfa_bytes(b"word\tw er d\t0.8\n")


def test_pls_subset_preserves_variants_roles_and_metadata() -> None:
    source = parse_pls_bytes(
        """<lexicon version="1.0" alphabet="ipa" xml:lang="en-US"
            xmlns:xml="http://www.w3.org/XML/1998/namespace">
          <lexeme><grapheme>read</grapheme><phoneme>ɹiːd</phoneme><phoneme>ɹɛd</phoneme></lexeme>
          <lexeme><grapheme>live</grapheme><role>verb</role><phoneme>lɪv</phoneme></lexeme>
        </lexicon>""".encode()
    )
    assert source.source.pronunciation_alphabet == "ipa"
    assert source.source.locale == "en-US"
    assert source.entries["read"] == ("ɹiːd", "ɹɛd")
    assert source.entries["live"]["verb"] == "lɪv"


def test_pls_rejects_unsupported_aliases() -> None:
    data = (
        b'<lexicon alphabet="ipa"><lexeme><grapheme>x</grapheme><alias>y</alias></lexeme></lexicon>'
    )
    with pytest.raises(ValueError, match="unsupported PLS construct"):
        parse_pls_bytes(data)


def test_external_adapter_data_round_trips_through_g2lex() -> None:
    source = parse_cmudict_bytes(b"hello HH AH L OW\nhello HH EH L OW\n")
    lexicon = open_bytes(pack_typed(TypedLexiconData(source.entries, source=source.source)))
    try:
        assert lexicon["hello"] == ("HH AH L OW", "HH EH L OW")
    finally:
        lexicon.close()


def test_gruut_sqlite_adapter_preserves_order_and_roles(tmp_path) -> None:
    path = tmp_path / "lexicon.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE word_phonemes (word TEXT, pron_order INTEGER, phonemes TEXT, role TEXT)"
        )
        connection.executemany(
            "INSERT INTO word_phonemes VALUES (?, ?, ?, ?)",
            [("read", 1, "r ɛ d", None), ("read", 2, "r i d", None), ("live", 1, "l ɪ v", "verb")],
        )
        connection.commit()
    source = parse_gruut_sqlite(path)
    assert source.entries["read"] == ("r ɛ d", "r i d")
    assert source.entries["live"]["verb"] == "l ɪ v"
    assert source.source.provider == "gruut"


def test_non_kokoro_fixture_full_round_trip(tmp_path: Path) -> None:
    source_path = Path(__file__).parent / "fixtures" / "generic.tsv"
    source = read_typed_lexicon(source_path, format="tsv")
    asset_path = tmp_path / "generic.g2lex"
    pack_file(source_path, asset_path, input_format="tsv")
    assert verify_file(source_path, asset_path, input_format="tsv")["lossless"]
    output = tmp_path / "generic.jsonl"
    export_file(asset_path, output, format="jsonl")
    assert read_typed_lexicon(output, format="jsonl").entries == source.entries
