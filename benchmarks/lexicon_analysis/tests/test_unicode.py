from __future__ import annotations

import unicodedata

from benchmarks.lexicon_analysis.analysis import unicode_statistics
from g2lex import SourceInfo, TypedLexiconData


def test_unicode_statistics_detects_keys_and_typed_pronunciations_without_mutation() -> None:
    decomposed = "e\u0301"
    source = TypedLexiconData(
        {decomposed: ("o\u0308",), "é": ("ö",)},
        SourceInfo("unicode"),
        physical_rows=2,
    )
    before = dict(source.entries)
    stats = unicode_statistics(source)
    assert stats["non_nfc_spellings"] == 1
    assert stats["non_nfc_pronunciation_strings"] == 1
    assert stats["nfc_distinct_spelling_count"] == 1
    assert stats["nfd_distinct_spelling_count"] == 1
    assert stats["nfc_collision_groups"] == 1
    assert source.entries == before
    assert set(source.entries) == {decomposed, unicodedata.normalize("NFC", decomposed)}
    assert source.entries[decomposed] != source.entries[unicodedata.normalize("NFC", decomposed)]
