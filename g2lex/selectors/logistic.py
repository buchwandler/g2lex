"""Deterministic hashed logistic candidate selection."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..runtime import ReconstructionCandidate
from .base import candidate_value


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


__all__ = ["HashedLogisticSelector", "train_hashed_logistic"]
