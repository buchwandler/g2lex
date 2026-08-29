"""Random forest candidate selection."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ..runtime import ReconstructionCandidate
from .base import candidate_value
from .tree import TreeSelector


@dataclass(frozen=True, slots=True)
class RandomForestSelector:
    trees: tuple[TreeSelector, ...]
    selector_id: str = "random-forest"

    def choose(
        self, word_features: Any, candidates: Sequence[ReconstructionCandidate]
    ) -> ReconstructionCandidate | None:
        votes: Counter[str] = Counter()
        for tree in self.trees:
            chosen = tree.choose(word_features, candidates)
            if chosen is not None:
                votes[chosen.stage_id] += 1
        if not votes:
            return None
        stage, _ = max(votes.items(), key=lambda item: (item[1], item[0]))
        return min(
            (candidate for candidate in candidates if candidate.stage_id == stage),
            key=candidate_value,
        )

    def as_dict(self):
        return {"selector_id": self.selector_id, "trees": [tree.as_dict() for tree in self.trees]}

    @property
    def serialized_bytes(self):
        return len(json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":")).encode())


ForestSelector = RandomForestSelector

__all__ = ["ForestSelector", "RandomForestSelector"]
