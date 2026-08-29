"""Dependency-neutral bounded search primitives."""

from __future__ import annotations


class SearchLimitError(RuntimeError):
    """A bounded search exceeded its configured state budget."""


def segmentation_rank(
    components: tuple[str, ...],
) -> tuple[int, tuple[int, ...], tuple[str, ...]]:
    """Historical ranking: fewer components, longer-leftmost, lexical tie break."""

    return (-len(components), tuple(map(len, components)), tuple(reversed(components)))


__all__ = ["SearchLimitError", "segmentation_rank"]
