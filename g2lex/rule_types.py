"""Dependency-neutral state shared by composition rules."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RuleStats:
    """Mutable counters collected while evaluating a composition rule."""

    usage_count: int = 0
    exact_success_count: int = 0
    mismatch_count: int = 0


__all__ = ["RuleStats"]
