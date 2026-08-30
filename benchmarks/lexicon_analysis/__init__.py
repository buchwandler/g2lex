"""Generic, source-neutral analysis tools for G2Lex lexica."""

from .analysis import (
    collision_groups,
    key_statistics,
    pronunciation_strings,
    source_shape,
    source_summary,
    unicode_statistics,
)
from .compare import compare_sources, conflict_samples, pairwise_sources

__all__ = [
    "collision_groups",
    "compare_sources",
    "conflict_samples",
    "key_statistics",
    "pairwise_sources",
    "pronunciation_strings",
    "source_shape",
    "source_summary",
    "unicode_statistics",
]
