"""Deterministic monotonic spelling to pronunciation alignment."""
from __future__ import annotations

from functools import lru_cache


def align(spelling: str, pronunciation: str, *, max_output_chunk_length: int = 4) -> tuple[tuple[str, str], ...]:
    if max_output_chunk_length < 0:
        raise ValueError("max_output_chunk_length must be non-negative")

    @lru_cache(maxsize=None)
    def solve(position: int, output_position: int) -> tuple[tuple[int, tuple[tuple[str, str], ...]], ...]:
        if position == len(spelling):
            return ((0, ()),) if output_position == len(pronunciation) else ()
        candidates: list[tuple[int, tuple[tuple[str, str], ...]]] = []
        for size in range(max_output_chunk_length + 1):
            end = output_position + size
            if end > len(pronunciation):
                break
            for cost, tail in solve(position + 1, end):
                chunk = pronunciation[output_position:end]
                penalty = 0 if chunk else 1
                candidates.append((cost + penalty, ((spelling[position], chunk), *tail)))
        candidates.sort(key=lambda item: (item[0], tuple(value[1] for value in item[1])))
        return tuple(candidates[:1])

    result = solve(0, 0)
    if not result:
        raise ValueError("spelling/pronunciation cannot be aligned with the configured chunk limit")
    return result[0][1]


align_spelling = align
