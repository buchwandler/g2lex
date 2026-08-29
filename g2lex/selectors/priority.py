"""Deterministic stage-priority candidate selection."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ..runtime import ReconstructionCandidate
from .base import choose_by_stage


@dataclass(frozen=True, slots=True)
class StaticPrioritySelector:
    order: tuple[str, ...] = ("compound", "morphology", "rewrite", "cart", "graphone", "neural")
    selector_id: str = "static-priority"

    def choose(
        self, word_features: Any, candidates: Sequence[ReconstructionCandidate]
    ) -> ReconstructionCandidate | None:
        return choose_by_stage(self.order, candidates)

    def as_dict(self):
        return {"selector_id": self.selector_id, "order": list(self.order)}

    @property
    def serialized_bytes(self):
        return len(json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":")).encode())


PrioritySelector = StaticPrioritySelector

__all__ = ["PrioritySelector", "StaticPrioritySelector"]
