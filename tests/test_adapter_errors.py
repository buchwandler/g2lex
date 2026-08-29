from __future__ import annotations

import pytest

from g2lex import WORD_ONLY, TaggedValue
from g2lex.adapters import (
    parse_jsonl_bytes,
    parse_kokoro_json_bytes,
    parse_mfa_bytes,
)


def test_jsonl_success_shapes_and_line_count() -> None:
    parsed = parse_jsonl_bytes(
        b'\n{"word":"a","kind":"word"}\n{"word":"b","kind":"scalar","value":""}\n'
        b'{"word":"c","kind":"list","value":["x","y"]}\n'
        b'{"word":"d","kind":"tagged","items":[["DEFAULT",null],["ALT",["x","y"]]]}\n'
    )
    assert parsed.entries == {
        "a": WORD_ONLY,
        "b": "",
        "c": ("x", "y"),
        "d": TaggedValue((("DEFAULT", None), ("ALT", ("x", "y")))),
    }
    assert parsed.physical_rows == 4


@pytest.mark.parametrize(
    "line, message",
    [
        ("not json", "invalid JSON"),
        ("[]", "non-empty word"),
        ('{"word":""}', "non-empty word"),
        ('{"word":"a","kind":"scalar","value":1}', "scalar value"),
        ('{"word":"a","kind":"list","value":"x"}', "list value"),
        ('{"word":"a","kind":"tagged","items":{}}', "tagged items"),
        ('{"word":"a","kind":"tagged","items":[[1,"x"]]}', "invalid tagged item"),
        ('{"word":"a","kind":"tagged","items":[["x",1]]}', "selector value"),
        ('{"word":"a","kind":"bad"}', "unsupported record kind"),
    ],
)
def test_jsonl_rejection_matrix_and_line_numbers(line: str, message: str) -> None:
    with pytest.raises(ValueError, match=message) as exc_info:
        parse_jsonl_bytes(("\n" + line + "\n").encode(), source_id="fixture")
    assert "fixture:2" in str(exc_info.value)


def test_jsonl_duplicate_and_invalid_utf8() -> None:
    with pytest.raises(ValueError, match="duplicate.*line 2|duplicate"):
        parse_jsonl_bytes(b'{"word":"a","kind":"word"}\n{"word":"a","kind":"word"}\n')
    with pytest.raises(ValueError, match="UTF-8"):
        parse_jsonl_bytes(b"\xff")


def test_kokoro_json_rejections_and_lists() -> None:
    assert parse_kokoro_json_bytes(b'{"a":["x","y"]}').entries["a"] == ("x", "y")
    with pytest.raises(TypeError, match="object"):
        parse_kokoro_json_bytes(b"[]")
    with pytest.raises(ValueError, match="UTF-8"):
        parse_kokoro_json_bytes(b"\xff")
    with pytest.raises(ValueError, match="lists are disabled"):
        parse_kokoro_json_bytes(b'{"a":["x"]}', allow_lists=False)
    with pytest.raises(ValueError, match="expected"):
        parse_kokoro_json_bytes(b'{"a":1}')
    with pytest.raises(ValueError, match="selector"):
        parse_kokoro_json_bytes(b'{"a":{"tag":[1]}}')


def test_mfa_shapes_comments_and_duplicate_variants() -> None:
    parsed = parse_mfa_bytes(b"# comment\na\tx y\na\tz\n; another\n")
    assert parsed.entries["a"] == ("x y", "z")
    assert parsed.physical_rows == 2
    with pytest.raises(ValueError, match="comments"):
        parse_mfa_bytes(b"# comment\n", comment_policy="error")
    with pytest.raises(ValueError, match="comment_policy"):
        parse_mfa_bytes(b"a\tx\n", comment_policy="bad")
    with pytest.raises(ValueError, match="UTF-8"):
        parse_mfa_bytes(b"\xff")
    for data, message in (
        (b"a\tx\ty\n", "probabilistic"),
        (b"a\n", "expected"),
        (b"\tx\n", "expected"),
        (b"a\t\n", "expected"),
    ):
        with pytest.raises(ValueError, match=message):
            parse_mfa_bytes(data)
