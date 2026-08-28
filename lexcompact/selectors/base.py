"""Shared bounded selector helpers."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..runtime import ReconstructionCandidate


def candidate_value(candidate: ReconstructionCandidate) -> tuple[Any, ...]:
    return (candidate.stage_id, candidate.rule_id or "", candidate.score if candidate.score is not None else 0)


def feature_value(features: Any, name: str, default: str = "") -> str:
    if isinstance(features, Mapping):
        return str(features.get(name, default))
    return str(getattr(features, name, default))


def choose_by_stage(order: Sequence[str], candidates: Sequence[ReconstructionCandidate]) -> ReconstructionCandidate | None:
    for stage in order:
        matching = [candidate for candidate in candidates if candidate.stage_id == stage]
        if matching:
            return min(matching, key=candidate_value)
    return min(candidates, key=candidate_value) if candidates else None
