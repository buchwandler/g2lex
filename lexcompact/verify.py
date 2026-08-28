"""Independent exact verification helpers."""

from __future__ import annotations

import random
from collections.abc import Iterable
from typing import Any

from .audit import audit_runtime_representation


def adversarial_misses(words: Iterable[str], *, limit: int = 256) -> tuple[str, ...]:
    known = set(words)
    candidates: list[str] = []
    for word in sorted(known):
        if len(word) > 1:
            candidates.append(word[:-1])
        candidates.extend((word + "x", word.swapcase(), word + "\u0301"))
        if len(word) > 1:
            candidates.append(word[1:] + word[:1])
        if len(candidates) >= limit * 4:
            break
    unique = sorted(set(candidates) - known)
    random.Random(0).shuffle(unique)
    return tuple(sorted(unique[:limit]))


def verify_candidate(
    candidate: Any, baseline: Any, *, miss_words: Iterable[str] | None = None
) -> dict[str, Any]:
    words = tuple(baseline.words)
    missing = pronunciation_mismatches = variant_count_mismatches = 0
    variant_order_mismatches = invariant_failures = 0
    for word in words:
        if not candidate.is_known(word):
            missing += 1
            continue
        expected = baseline.lookup_all(word)
        try:
            actual = candidate.lookup_all(word)
        except (IndexError, KeyError, RuntimeError):
            invariant_failures += 1
            continue
        if len(actual) != len(expected):
            variant_count_mismatches += 1
        elif actual != expected:
            variant_order_mismatches += 1
        if actual != expected:
            pronunciation_mismatches += 1
    misses = tuple(miss_words or adversarial_misses(words))
    false_positives = sum(candidate.is_known(word) for word in misses)
    audit = audit_runtime_representation(candidate)
    lossless = not any(
        (
            missing,
            false_positives,
            pronunciation_mismatches,
            variant_count_mismatches,
            variant_order_mismatches,
            invariant_failures,
        )
    )
    return {
        "words_checked": len(words),
        "variants_checked": sum(len(baseline.lookup_all(word)) for word in words),
        "missing_words": missing,
        "extra_words": false_positives,
        "pronunciation_mismatches": pronunciation_mismatches,
        "variant_count_mismatches": variant_count_mismatches,
        "variant_order_mismatches": variant_order_mismatches,
        "membership_false_negatives": missing,
        "membership_false_positives": false_positives,
        "invariant_failures": invariant_failures,
        "lossless": lossless,
        "audit": audit,
        "miss_words_checked": len(misses),
    }
