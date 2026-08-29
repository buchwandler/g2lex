"""Predicate-based tree candidate selection."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ..runtime import ReconstructionCandidate
from .base import candidate_value, choose_by_stage, feature_value
from .priority import StaticPrioritySelector


@dataclass(frozen=True, slots=True)
class TreePredicate:
    feature: str
    value: str
    stage_id: str


@dataclass(frozen=True, slots=True)
class TreeSelector:
    predicates: tuple[TreePredicate, ...] = ()
    default_order: tuple[str, ...] = StaticPrioritySelector().order
    selector_id: str = "tree"

    def choose(
        self, word_features: Any, candidates: Sequence[ReconstructionCandidate]
    ) -> ReconstructionCandidate | None:
        for predicate in self.predicates:
            if feature_value(word_features, predicate.feature) == predicate.value:
                matching = [
                    candidate for candidate in candidates if candidate.stage_id == predicate.stage_id
                ]
                if matching:
                    return min(matching, key=candidate_value)
        return choose_by_stage(self.default_order, candidates)

    def as_dict(self):
        return {
            "selector_id": self.selector_id,
            "predicates": [[p.feature, p.value, p.stage_id] for p in self.predicates],
            "default_order": list(self.default_order),
        }

    @property
    def serialized_bytes(self):
        return len(json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":")).encode())


CARTSelector = TreeSelector

__all__ = ["CARTSelector", "TreePredicate", "TreeSelector"]
