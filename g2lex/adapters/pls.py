"""Strict lossless subset adapter for W3C Pronunciation Lexicons."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from ..model import SourceInfo, TypedLexiconData
from ..value import LexiconValue, TaggedValue

_XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def _name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _text(element: ET.Element, label: str) -> str:
    if element.attrib or list(element):
        raise ValueError(f"unsupported PLS construct: {label} attributes or nested content")
    value = element.text or ""
    if not value:
        raise ValueError(f"PLS {label} must not be empty")
    return value


def parse_pls_bytes(
    data: bytes,
    *,
    path: Path | None = None,
    source_id: str | None = None,
) -> TypedLexiconData:
    """Parse the supported PLS v1 subset without flattening richer records."""
    try:
        root = ET.fromstring(data)
    except (ET.ParseError, UnicodeDecodeError) as exc:
        raise ValueError("PLS input is not valid XML") from exc
    if _name(root) != "lexicon":
        raise ValueError("PLS root element must be lexicon")

    allowed_root = {"version", "alphabet", "lang", _XML_LANG}
    unsupported_root = set(root.attrib) - allowed_root
    if unsupported_root:
        raise ValueError(
            f"unsupported PLS construct: lexicon attributes {sorted(unsupported_root)}"
        )
    alphabet = root.attrib.get("alphabet")
    if not alphabet:
        raise ValueError("PLS lexicon must declare one default alphabet")
    language = root.attrib.get(_XML_LANG, root.attrib.get("lang"))

    entries: dict[str, LexiconValue] = {}
    lexeme_count = 0
    for lexeme in root:
        if _name(lexeme) != "lexeme":
            raise ValueError(f"unsupported PLS construct: {_name(lexeme)}")
        graphemes = []
        phonemes = []
        roles = []
        for child in lexeme:
            name = _name(child)
            if name == "grapheme":
                graphemes.append(_text(child, "grapheme"))
            elif name == "phoneme":
                if child.attrib:
                    raise ValueError("unsupported PLS construct: per-phoneme attributes")
                phonemes.append(_text(child, "phoneme"))
            elif name in {"role", "part-of-speech"}:
                roles.append(_text(child, name))
            else:
                raise ValueError(f"unsupported PLS construct: lexeme/{name}")
        if len(graphemes) != 1:
            raise ValueError("unsupported PLS construct: each lexeme must have one grapheme")
        if not phonemes:
            raise ValueError("PLS lexeme must have at least one phoneme")
        if len(roles) > 1:
            raise ValueError("unsupported PLS construct: multiple roles per lexeme")
        word = graphemes[0]
        value: str | tuple[str, ...] = phonemes[0] if len(phonemes) == 1 else tuple(phonemes)
        role = roles[0] if roles else None
        previous = entries.get(word)
        if previous is None:
            entries[word] = TaggedValue(((role, value),)) if role is not None else value
        elif role is None and isinstance(previous, tuple):
            entries[word] = previous + tuple(phonemes)
        elif role is not None and isinstance(previous, TaggedValue):
            try:
                old = previous[role]
            except KeyError:
                entries[word] = TaggedValue(previous.items + ((role, value),))
            else:
                old_values = (old,) if isinstance(old, str) else (old or ())
                entries[word] = TaggedValue(
                    tuple(
                        (tag, old_values + tuple(phonemes) if tag == role else selector)
                        for tag, selector in previous.items
                    )
                )
        else:
            raise ValueError("unsupported PLS construct: mixed tagged and untagged pronunciations")
        lexeme_count += 1

    source = SourceInfo(
        source_id=source_id or (path.stem if path else "pls"),
        language=language,
        locale=language if language and "-" in language else None,
        pronunciation_alphabet=alphabet,
        source_format="pls",
        format="pls",
        path=str(path) if path else None,
        size_bytes=len(data),
    )
    return TypedLexiconData(
        entries,
        source=source,
        physical_rows=lexeme_count,
        metadata={"pls_subset": "lexeme-grapheme-phoneme-role"},
    )
