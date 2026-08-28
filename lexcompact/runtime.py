"""Shared runtime abstractions for exact, oracle-free reconstruction."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from .model import PronunciationTuple


@dataclass(frozen=True, slots=True)
class ReconstructionCandidate:
    """Ephemeral output from a shared reconstructor.

    The queried spelling is deliberately not part of this object. Candidates
    are lookup-local values and are never runtime word-indexed records.
    """

    stage_id: str
    pronunciation: PronunciationTuple
    rule_id: str | None = None
    score: int | None = None
    component_count: int | None = None
    analysis_kind: str | None = None
    feature_bits: int = 0


class Reconstructor(Protocol):
    stage_id: str
    version: str

    def candidates(self, word: str, context: Any) -> tuple[ReconstructionCandidate, ...]: ...

    def as_dict(self) -> Mapping[str, object]: ...

    def serialize_sections(self) -> Mapping[str, bytes]: ...


class CandidateSelector(Protocol):
    selector_id: str

    def choose(
        self,
        word_features: Any,
        candidates: Sequence[ReconstructionCandidate],
    ) -> ReconstructionCandidate | None: ...


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


ResolvedValues = OverlayMapping


@dataclass(slots=True)
class RuntimeProgram:
    """Bounded shared reconstruction program.

    ``legacy_composer`` is a compatibility adapter for V3 assets. New stages
    can provide reconstructors and a selector without exposing source answers.
    """

    reconstructors: tuple[Reconstructor, ...] = ()
    selector: CandidateSelector | None = None
    recursive_components: bool = False
    max_recursive_depth: int = 4
    max_states: int = 100_000
    legacy_composer: Any | None = None

    @classmethod
    def from_composer(cls, composer: Any) -> "RuntimeProgram":
        return cls(
            recursive_components=bool(composer.recursive_components),
            max_recursive_depth=int(composer.max_recursive_depth),
            max_states=int(composer.max_states),
            legacy_composer=composer,
        )

    def reconstruct(
        self,
        word: str,
        *,
        literals: Mapping[str, PronunciationTuple],
        membership: Any,
        context: Any | None = None,
        prefix_index: Any | None = None,
        resolver: Any | None = None,
    ) -> PronunciationTuple | None:
        if self.legacy_composer is not None:
            return self.legacy_composer.derive(
                word,
                literals=literals,
                prefix_index=prefix_index,
                resolver=resolver,
                context=context,
            )
        candidates: list[ReconstructionCandidate] = []
        for reconstructor in self.reconstructors:
            candidates.extend(reconstructor.candidates(word, context))
        if not candidates:
            return None
        if self.selector is None:
            return candidates[0].pronunciation
        selected = self.selector.choose({}, tuple(candidates))
        return selected.pronunciation if selected is not None else None

    def as_dict(self) -> dict[str, object]:
        return {
            "version": "1",
            "recursive_components": self.recursive_components,
            "max_recursive_depth": self.max_recursive_depth,
            "max_states": self.max_states,
            "reconstructors": [dict(item.as_dict()) for item in self.reconstructors],
            "selector": getattr(self.selector, "selector_id", None),
        }

    def serialize_sections(self) -> Mapping[str, bytes]:
        import json

        return {"runtime-program.json": json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":")).encode()}
