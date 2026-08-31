from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from g2lex import open, pack_file, read_typed_lexicon, verify_file
from g2lex.adapters import parse_ipa_tsv_bytes


def test_ipa_tsv_strips_one_outer_pair_and_preserves_internal_slash() -> None:
    parsed = parse_ipa_tsv_bytes("Haus\t/haʊs/\npath\t/abc/def/\n".encode())

    assert parsed.entries == {"Haus": ("ha\u028as",), "path": ("abc/def",)}


def test_ipa_tsv_recognizes_only_first_row_headers() -> None:
    parsed = parse_ipa_tsv_bytes("word\tespeak_ipa\nword\t/wɜːd/\nipa\t/ipa/\n".encode())

    assert parsed.entries == {"word": ("w\u025c\u02d0d",), "ipa": ("ipa",)}
    assert parsed.physical_rows == 3


def test_ipa_tsv_preserves_duplicate_variant_order() -> None:
    parsed = parse_ipa_tsv_bytes("read\t/r/\nread\t/rɛ/\nread\t/r/\n".encode())

    assert parsed.entries["read"] == ("r", "r\u025b", "r")


def test_ipa_tsv_rejects_malformed_rows() -> None:
    with pytest.raises(ValueError, match="expected two or three tab-separated fields"):
        parse_ipa_tsv_bytes(b"word\t/ipa/\textra\tmore\n")
    with pytest.raises(ValueError, match="empty spelling"):
        parse_ipa_tsv_bytes(b"\t/ipa/\n")


def test_ipa_tsv_accepts_source_annotation_field() -> None:
    parsed = parse_ipa_tsv_bytes("Backend\t/bɛkɛnd/\tNOUN\n".encode())

    assert parsed.entries == {"Backend": ("bɛkɛnd",)}


def test_ipa_tsv_source_info_hashes_raw_bytes(tmp_path: Path) -> None:
    data = "Haus\t/haʊs/\n".encode()
    source_path = tmp_path / "source.tsv"
    source_path.write_bytes(data)

    parsed = read_typed_lexicon(source_path, format="ipa-tsv", source_id="fixture")

    assert parsed.source.format == "ipa-tsv"
    assert parsed.source.sha256 == hashlib.sha256(data).hexdigest()
    assert parsed.source.size_bytes == len(data)


def test_ipa_tsv_pack_verify_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "source.tsv"
    source.write_text("word\tespeak_ipa\nHaus\t/haʊs/\n", encoding="utf-8")
    asset = tmp_path / "asset.g2lex"

    pack_file(source, asset, input_format="ipa-tsv", source_id="fixture")
    assert verify_file(source, asset, input_format="ipa-tsv")["lossless"]
    lexicon = open(asset)
    try:
        assert lexicon.get("word") is None
        assert lexicon.get("Haus") == ("haʊs",)
        assert lexicon.metadata["source"]["source_format"] == "ipa-tsv"
    finally:
        lexicon.close()
