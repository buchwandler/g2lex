"""Gradient-boosted tree candidate selection."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ..runtime import ReconstructionCandidate
from .base import candidate_value


@dataclass(frozen=True, slots=True)
class GradientBoostedTreeSelector:
    stage_scores: tuple[tuple[str, int], ...] = ()
    selector_id: str = "gbdt"

    def choose(
        self, word_features: Any, candidates: Sequence[ReconstructionCandidate]
    ) -> ReconstructionCandidate | None:
        scores = dict(self.stage_scores)
        return (
            max(
                candidates,
                key=lambda candidate: (
                    scores.get(candidate.stage_id, 0),
                    tuple(reversed(candidate_value(candidate))),
                ),
            )
            if candidates
            else None
        )

    def as_dict(self):
        return {"selector_id": self.selector_id, "stage_scores": list(self.stage_scores)}

    @property
    def serialized_bytes(self):
        return len(json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":")).encode())


GBDTSelector = GradientBoostedTreeSelector

__all__ = ["GBDTSelector", "GradientBoostedTreeSelector"]
