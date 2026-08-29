from __future__ import annotations

import pytest

from g2lex.adapters.pls import parse_pls_bytes
from g2lex.value import TaggedValue


def _pls(body: str, attrs: str = 'version="1.0" alphabet="ipa"') -> bytes:
    return f"<lexicon {attrs}>{body}</lexicon>".encode()


def test_pls_success_ordering_metadata_and_duplicate_variants() -> None:
    data = _pls(
        "<lexeme><grapheme>a</grapheme><phoneme>x</phoneme><phoneme>y</phoneme></lexeme>"
        "<lexeme><grapheme>b</grapheme><role>NOUN</role><phoneme>b</phoneme></lexeme>"
        "<lexeme><grapheme>b</grapheme><role>NOUN</role><phoneme>p</phoneme></lexeme>"
        "<lexeme><grapheme>b</grapheme><role>VERB</role><phoneme>v</phoneme></lexeme>"
    )
    parsed = parse_pls_bytes(data, source_id="fixture")
    assert parsed.entries["a"] == ("x", "y")
    assert parsed.entries["b"] == TaggedValue((("NOUN", ("b", "p")), ("VERB", "v")))
    assert parsed.physical_rows == 4
    assert parsed.source.source_id == "fixture"
    assert parsed.source.pronunciation_alphabet == "ipa"


@pytest.mark.parametrize(
    "data, message",
    [
        (b"not xml", "valid XML"),
        (_pls("", 'version="1.0"'), "default alphabet"),
        (
            _pls(
                "<entry/>",
            ),
            "entry",
        ),
        (_pls("<lexeme><grapheme>a</grapheme></lexeme>"), "at least one"),
        (
            _pls(
                "<lexeme><grapheme>a</grapheme><grapheme>b</grapheme><phoneme>x</phoneme></lexeme>"
            ),
            "one grapheme",
        ),
        (
            _pls(
                "<lexeme><grapheme>a</grapheme><phoneme>x</phoneme><phoneme>y</phoneme><role>N</role><role>V</role></lexeme>"
            ),
            "multiple roles",
        ),
        (_pls('<lexeme><grapheme a="1">a</grapheme><phoneme>x</phoneme></lexeme>'), "attributes"),
        (_pls("<lexeme><grapheme>a<b>x</b></grapheme><phoneme>x</phoneme></lexeme>"), "nested"),
        (_pls('<lexeme><grapheme>a</grapheme><phoneme p="1">x</phoneme></lexeme>'), "per-phoneme"),
        (_pls("<lexeme><grapheme></grapheme><phoneme>x</phoneme></lexeme>"), "must not be empty"),
        (_pls("<lexeme><grapheme>a</grapheme><phoneme>x</phoneme></lexeme><other/>"), "other"),
        (
            _pls(
                "<lexeme><grapheme>a</grapheme><phoneme>x</phoneme></lexeme>",
                'version="1" alphabet="ipa" bad="x"',
            ),
            "attributes",
        ),
    ],
)
def test_pls_rejection_matrix(data: bytes, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_pls_bytes(data)


def test_pls_duplicate_and_mixed_shapes_are_rejected() -> None:
    duplicate = _pls(
        "<lexeme><grapheme>a</grapheme><phoneme>x</phoneme></lexeme>"
        "<lexeme><grapheme>a</grapheme><phoneme>y</phoneme></lexeme>"
    )
    # Two untagged scalar rows are intentionally not losslessly representable by this subset.
    with pytest.raises(ValueError, match="mixed"):
        parse_pls_bytes(duplicate)
    mixed = _pls(
        "<lexeme><grapheme>a</grapheme><role>N</role><phoneme>x</phoneme></lexeme>"
        "<lexeme><grapheme>a</grapheme><phoneme>y</phoneme></lexeme>"
    )
    with pytest.raises(ValueError, match="mixed"):
        parse_pls_bytes(mixed)
    with pytest.raises(ValueError, match="valid XML"):
        parse_pls_bytes(b"<lexicon alphabet='ipa'>\xff</lexicon>")
