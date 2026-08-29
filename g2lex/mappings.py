"""Dependency-neutral mapping primitives."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .types import PronunciationTuple


@dataclass(slots=True)
class OverlayMapping(Mapping[str, PronunciationTuple]):
    """Read-only lookup overlay without copying the base mapping."""

    base: Mapping[str, PronunciationTuple]
    overlay: Mapping[str, PronunciationTuple] = field(default_factory=dict)

    def __getitem__(self, key: str) -> PronunciationTuple:
        if key in self.overlay:
            return self.overlay[key]
        return self.base[key]

    def __iter__(self):
        seen = set(self.overlay)
        yield from self.overlay
        yield from (key for key in self.base if key not in seen)

    def __len__(self) -> int:
        return len(self.overlay) + sum(key not in self.overlay for key in self.base)

    def __contains__(self, key: object) -> bool:
        return key in self.overlay or key in self.base

    def get(self, key: str, default: Any = None) -> Any:
        if key in self.overlay:
            return self.overlay[key]
        return self.base.get(key, default)


__all__ = ["OverlayMapping"]
