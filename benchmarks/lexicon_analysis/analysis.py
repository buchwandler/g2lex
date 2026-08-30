"""Analysis-only statistics for exact typed G2Lex source models.

The transforms in this module are deliberately never applied to lookup data.
They describe possible collisions for consumers that may choose to normalize.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from g2lex.value import TaggedValue

_TRANSFORMS: dict[str, Callable[[str], str]] = {
    "exact": lambda value: value,
    "lower": str.lower,
    "casefold": str.casefold,
    "nfc": lambda value: unicodedata.normalize("NFC", value),
    "nfd": lambda value: unicodedata.normalize("NFD", value),
}


def _entries(source: Mapping[str, Any] | object) -> Mapping[str, Any]:
    entries = getattr(source, "entries", None)
    if isinstance(entries, Mapping):
        return entries
    if isinstance(source, Mapping):
        return source
    raise TypeError("source must expose entries or implement Mapping")


def _metadata(source: object) -> Mapping[str, object]:
    metadata = getattr(source, "metadata", {})
    return metadata if isinstance(metadata, Mapping) else {}


def pronunciation_strings(value: object) -> tuple[str, ...]:
    """Recursively return pronunciation-bearing strings without normalization."""
    if isinstance(value, str):
        return (value,)
    if isinstance(value, tuple):
        return tuple(item for item in value if isinstance(item, str))
    if isinstance(value, TaggedValue):
        result: list[str] = []
        for selector in value.values():
            result.extend(pronunciation_strings(selector))
        return tuple(result)
    return ()


def collision_groups(
    words: Iterable[str], transform: Callable[[str], str]
) -> dict[str, tuple[str, ...]]:
    """Group distinct raw spellings that share an analysis key.

    Duplicate raw values are retained in the input group, which makes this
    helper useful for row-level diagnostics as well as mapping keys.
    """
    groups: dict[str, list[str]] = {}
    for word in words:
        groups.setdefault(transform(word), []).append(word)
    return {key: tuple(sorted(values)) for key, values in sorted(groups.items()) if len(values) > 1}


def key_statistics(source: Mapping[str, Any] | object) -> dict[str, object]:
    """Report collision groups for exact, casing, and Unicode analysis keys."""
    words = tuple(_entries(source))
    result: dict[str, object] = {}
    for name, transform in _TRANSFORMS.items():
        groups = collision_groups(words, transform)
        result[f"{name}_collision_groups"] = len(groups)
        result[f"{name}_collisions"] = groups
    return result


def unicode_statistics(source: Mapping[str, Any] | object) -> dict[str, object]:
    """Measure Unicode equivalence without mutating source keys or values."""
    entries = _entries(source)
    words = tuple(entries)
    values = tuple(
        pronunciation
        for value in entries.values()
        for pronunciation in pronunciation_strings(value)
    )
    nfc_groups = collision_groups(words, lambda value: unicodedata.normalize("NFC", value))
    return {
        "non_nfc_spellings": sum(unicodedata.normalize("NFC", word) != word for word in words),
        "non_nfc_pronunciation_strings": sum(
            unicodedata.normalize("NFC", value) != value for value in values
        ),
        "nfc_distinct_spelling_count": len({unicodedata.normalize("NFC", word) for word in words}),
        "nfd_distinct_spelling_count": len({unicodedata.normalize("NFD", word) for word in words}),
        "nfc_collision_groups": len(nfc_groups),
        "nfc_collisions": nfc_groups,
    }


def source_shape(source: Mapping[str, Any] | object) -> dict[str, int]:
    """Return physical-row and typed-value shape metrics for one source."""
    entries = _entries(source)
    physical_rows = getattr(source, "physical_rows", None)
    values = tuple(entries.values())
    pronunciation_value_count = sum(len(pronunciation_strings(value)) for value in values)
    duplicate_rows = 0
    for value in values:
        variants = pronunciation_strings(value)
        duplicate_rows += len(variants) - len(set(variants))
    return {
        "physical_rows": int(
            physical_rows if physical_rows is not None else pronunciation_value_count
        ),
        "logical_spellings": len(entries),
        "pronunciation_value_count": pronunciation_value_count,
        "multi_variant_words": sum(len(pronunciation_strings(value)) > 1 for value in values),
        "maximum_variant_count": max(
            (len(pronunciation_strings(value)) for value in values), default=0
        ),
        "duplicate_identical_rows": duplicate_rows,
    }


def source_summary(
    source: Mapping[str, Any] | object, *, source_name: str | None = None
) -> dict[str, object]:
    """Combine provenance, shape, key, and Unicode metrics for one source."""
    info = getattr(source, "source", None)
    if info is not None and hasattr(info, "canonical_dict"):
        provenance = dict(info.canonical_dict())
    elif isinstance(info, Mapping):
        provenance = dict(info)
    elif info is not None:
        provenance = {
            key: getattr(info, key)
            for key in (
                "source_id",
                "revision",
                "sha256",
                "license",
                "format",
                "path",
                "size_bytes",
            )
            if hasattr(info, key)
        }
    else:
        provenance = {}
    return {
        "source": source_name or provenance.get("source_id"),
        "provenance": provenance,
        "metadata": dict(_metadata(source)),
        "shape": source_shape(source),
        "keys": key_statistics(source),
        "unicode": unicode_statistics(source),
    }


__all__ = [
    "collision_groups",
    "key_statistics",
    "pronunciation_strings",
    "source_shape",
    "source_summary",
    "unicode_statistics",
]
