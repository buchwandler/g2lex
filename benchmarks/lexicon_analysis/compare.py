"""Pairwise typed lexicon comparison and theoretical sharing metrics."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Mapping
from itertools import combinations
from typing import Any

from .analysis import pronunciation_strings


def _entries(source: Mapping[str, Any] | object) -> Mapping[str, Any]:
    entries = getattr(source, "entries", None)
    if isinstance(entries, Mapping):
        return entries
    if isinstance(source, Mapping):
        return source
    raise TypeError("source must expose entries or implement Mapping")


def _name(source: object, fallback: str) -> str:
    info = getattr(source, "source", None)
    return str(getattr(info, "source_id", fallback))


def _keyset(source: object, transform) -> set[str]:
    return {transform(word) for word in _entries(source)}


def _variant_class(left: tuple[str, ...], right: tuple[str, ...]) -> str:
    if left == right:
        return "same_ordered_tuple"
    if set(left) == set(right):
        return "same_unordered_variant_set"
    if set(left) & set(right):
        return "partial_variant_overlap"
    return "no_variant_overlap"


def _entry_rows(left: object, right: object) -> list[dict[str, object]]:
    left_entries, right_entries = _entries(left), _entries(right)
    rows: list[dict[str, object]] = []
    for word in sorted(set(left_entries) & set(right_entries)):
        left_value, right_value = left_entries[word], right_entries[word]
        left_variants = pronunciation_strings(left_value)
        right_variants = pronunciation_strings(right_value)
        exact_typed = left_value == right_value
        any_overlap = bool(set(left_variants) & set(right_variants))
        rows.append(
            {
                "word": word,
                "left": left_value,
                "right": right_value,
                "exact_typed": exact_typed,
                "pronunciation_any_variant": any_overlap,
                "variant_class": _variant_class(left_variants, right_variants),
                "shape_conflict": type(left_value) is not type(right_value),
                "value_conflict": not exact_typed and not any_overlap,
            }
        )
    return rows


def conflict_samples(left: object, right: object, *, limit: int = 1000) -> list[dict[str, object]]:
    """Return deterministic raw-spelling conflict examples, bounded only for output."""
    if limit < 0:
        raise ValueError("conflict limit must be non-negative")
    return [
        row
        for row in _entry_rows(left, right)
        if not row["exact_typed"] or not row["pronunciation_any_variant"]
    ][:limit]


def compare_sources(
    left: object, right: object, *, conflict_limit: int = 1000
) -> dict[str, object]:
    """Compare two exact typed sources without flattening tagged values."""
    left_entries, right_entries = _entries(left), _entries(right)
    common = set(left_entries) & set(right_entries)
    rows = _entry_rows(left, right)
    exact_typed = sum(bool(row["exact_typed"]) for row in rows)
    any_variant = sum(bool(row["pronunciation_any_variant"]) for row in rows)
    counts = {
        "same_ordered_tuple": sum(row["variant_class"] == "same_ordered_tuple" for row in rows),
        "same_unordered_variant_set": sum(
            row["variant_class"] == "same_unordered_variant_set" for row in rows
        ),
        "partial_variant_overlap": sum(
            row["variant_class"] == "partial_variant_overlap" for row in rows
        ),
        "no_variant_overlap": sum(row["variant_class"] == "no_variant_overlap" for row in rows),
    }
    union = set(left_entries) | set(right_entries)
    return {
        "source_a": _name(left, "a"),
        "source_b": _name(right, "b"),
        "logical_entry_count_a": len(left_entries),
        "logical_entry_count_b": len(right_entries),
        "exact_spelling_intersection": len(common),
        "exact_spelling_union": len(union),
        "jaccard_overlap": len(common) / len(union) if union else 0.0,
        "lowercase_key_intersection": len(_keyset(left, str.lower) & _keyset(right, str.lower)),
        "casefold_key_intersection": len(
            _keyset(left, str.casefold) & _keyset(right, str.casefold)
        ),
        "nfc_key_intersection": len(
            _keyset(left, lambda value: unicodedata.normalize("NFC", value))
            & _keyset(right, lambda value: unicodedata.normalize("NFC", value))
        ),
        "exact_typed_agreement": exact_typed,
        "pronunciation_any_variant_agreement": any_variant,
        "shape_conflicts": sum(bool(row["shape_conflict"]) for row in rows),
        "value_conflicts": sum(bool(row["value_conflict"]) for row in rows),
        "variant_agreement": counts,
        "conflicting_overlapping_entries": sum(not row["exact_typed"] for row in rows),
        "conflicts": conflict_samples(left, right, limit=conflict_limit),
    }


def pairwise_sources(
    sources: Mapping[str, object] | Iterable[tuple[str, object]], *, conflict_limit: int = 1000
) -> list[dict[str, object]]:
    """Compare all source pairs in deterministic source-name order."""
    items = dict(sources)
    return [
        compare_sources(items[left], items[right], conflict_limit=conflict_limit)
        for left, right in combinations(sorted(items), 2)
    ]


def cross_source_sharing(
    sources: Mapping[str, object] | Iterable[tuple[str, object]],
) -> dict[str, object]:
    """Report theoretical duplicate content; never build a merged asset."""
    items = dict(sources)
    pairs = []
    identical_typed = shared_variant = shared_strings = 0
    for left_name, right_name in combinations(sorted(items), 2):
        left, right = items[left_name], items[right_name]
        left_entries, right_entries = _entries(left), _entries(right)
        common = set(left_entries) & set(right_entries)
        typed = sum(left_entries[word] == right_entries[word] for word in common)
        variants = sum(
            bool(
                set(pronunciation_strings(left_entries[word]))
                & set(pronunciation_strings(right_entries[word]))
            )
            for word in common
        )
        strings = len(
            {value for raw in left_entries.values() for value in pronunciation_strings(raw)}
            & {value for raw in right_entries.values() for value in pronunciation_strings(raw)}
        )
        identical_typed += typed
        shared_variant += variants
        shared_strings += strings
        pairs.append(
            {
                "source_a": left_name,
                "source_b": right_name,
                "identical_spelling_identical_typed_value": typed,
                "identical_spelling_shared_pronunciation_variant": variants,
                "identical_pronunciation_strings": strings,
            }
        )
    return {
        "identical_spelling_identical_typed_value": identical_typed,
        "identical_spelling_shared_pronunciation_variant": shared_variant,
        "identical_pronunciation_strings_used_by_multiple_sources": shared_strings,
        "pairs": pairs,
        "note": "Theoretical sharing only; source provenance and licensing remain independent.",
    }


__all__ = ["compare_sources", "conflict_samples", "cross_source_sharing", "pairwise_sources"]
