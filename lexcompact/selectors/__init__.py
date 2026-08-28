"""Deterministic candidate selectors with bounded pure-data state."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..runtime import ReconstructionCandidate
from .base import candidate_value, choose_by_stage, feature_value


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
                    candidate
                    for candidate in candidates
                    if candidate.stage_id == predicate.stage_id
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


@dataclass(frozen=True, slots=True)
class HashedLogisticSelector:
    weights: tuple[tuple[int, tuple[tuple[str, int], ...]], ...] = ()
    bucket_count: int = 1024
    selector_id: str = "hashed-logistic"

    def _score(self, candidate: ReconstructionCandidate, features: Any) -> int:
        score = 0
        feature_items = features.items() if isinstance(features, Mapping) else ()
        for name, value in feature_items:
            bucket = (
                int.from_bytes(
                    hashlib.blake2b(
                        f"{name}={value}".encode(), digest_size=4, person=b"lxc-logit"
                    ).digest(),
                    "little",
                )
                % self.bucket_count
            )
            for candidate_bucket, stage_weights in self.weights:
                if candidate_bucket == bucket:
                    score += dict(stage_weights).get(candidate.stage_id, 0)
        return score

    def choose(
        self, word_features: Any, candidates: Sequence[ReconstructionCandidate]
    ) -> ReconstructionCandidate | None:
        return (
            max(
                candidates,
                key=lambda candidate: (
                    self._score(candidate, word_features),
                    tuple(reversed(candidate_value(candidate))),
                ),
            )
            if candidates
            else None
        )

    def as_dict(self):
        return {
            "selector_id": self.selector_id,
            "bucket_count": self.bucket_count,
            "weights": [[bucket, list(values)] for bucket, values in self.weights],
        }

    @property
    def serialized_bytes(self):
        return len(json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":")).encode())


def train_hashed_logistic(
    rows: Iterable[Mapping[str, Any]], *, bucket_count: int = 1024, max_bytes: int = 32768
) -> HashedLogisticSelector:
    counts: dict[int, Counter[str]] = {}
    for row in rows:
        features = row.get("features", {})
        target = str(row["target_stage"])
        for name, value in features.items() if isinstance(features, Mapping) else ():
            bucket = (
                int.from_bytes(
                    hashlib.blake2b(
                        f"{name}={value}".encode(), digest_size=4, person=b"lxc-logit"
                    ).digest(),
                    "little",
                )
                % bucket_count
            )
            counts.setdefault(bucket, Counter())[target] += 1
    weights = tuple(
        (bucket, tuple(sorted(counter.items()))) for bucket, counter in sorted(counts.items())
    )
    selector = HashedLogisticSelector(weights, bucket_count)
    if selector.serialized_bytes > max_bytes:
        raise ValueError("logistic selector exceeds byte budget")
    return selector


@dataclass(frozen=True, slots=True)
class RandomForestSelector:
    trees: tuple[TreeSelector, ...]
    selector_id: str = "random-forest"

    def choose(
        self, word_features: Any, candidates: Sequence[ReconstructionCandidate]
    ) -> ReconstructionCandidate | None:
        votes = Counter(
            tree.choose(word_features, candidates).stage_id
            for tree in self.trees
            if tree.choose(word_features, candidates) is not None
        )
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


ForestSelector = RandomForestSelector
GBDTSelector = GradientBoostedTreeSelector
PrioritySelector = StaticPrioritySelector
CARTSelector = TreeSelector

__all__ = [
    "CARTSelector",
    "ForestSelector",
    "GBDTSelector",
    "GradientBoostedTreeSelector",
    "HashedLogisticSelector",
    "PrioritySelector",
    "RandomForestSelector",
    "StaticPrioritySelector",
    "TreePredicate",
    "TreeSelector",
    "train_hashed_logistic",
]
