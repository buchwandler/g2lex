"""Shared runtime abstractions for exact, oracle-free reconstruction."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from .model import PronunciationTuple


@dataclass(frozen=True, slots=True)
class ReconstructionCandidate:
    """Ephemeral output from a shared reconstructor."""

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
        self, word_features: Any, candidates: Sequence[ReconstructionCandidate]
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


class ComposerReconstructor:
    """V4 adapter exposing the shared composer as an ephemeral stage."""

    stage_id = "compound"
    version = "1"

    def __init__(self, composer: Any, stage_id: str = "compound") -> None:
        self.composer = composer
        self.stage_id = stage_id

    def candidates(self, word: str, context: Any) -> tuple[ReconstructionCandidate, ...]:
        values = context if isinstance(context, Mapping) else {}
        result = self.composer.derive_result(
            word,
            literals=values["literals"],
            prefix_index=values.get("prefix_index"),
            resolver=values.get("resolver"),
            context=values.get("base_context"),
        )
        if result is None:
            return ()
        return (
            ReconstructionCandidate(
                self.stage_id,
                result.pronunciation,
                result.rule_id,
                component_count=len(result.components),
                analysis_kind="composer",
            ),
        )

    def as_dict(self) -> Mapping[str, object]:
        return {"stage_id": self.stage_id, "version": self.version, "kind": "composer-adapter"}

    def serialize_sections(self) -> Mapping[str, bytes]:
        return {
            "reconstructor.compound.json": json.dumps(
                self.as_dict(), sort_keys=True, separators=(",", ":")
            ).encode()
        }


@dataclass(slots=True)
class RuntimeProgram:
    """Bounded shared reconstruction program."""

    reconstructors: tuple[Reconstructor, ...] = ()
    selector: CandidateSelector | None = None
    recursive_components: bool = False
    max_recursive_depth: int = 4
    max_states: int = 100_000
    legacy_composer: Any | None = None

    @classmethod
    def from_composer(cls, composer: Any) -> RuntimeProgram:
        return cls(
            recursive_components=bool(composer.recursive_components),
            max_recursive_depth=int(composer.max_recursive_depth),
            max_states=int(composer.max_states),
            legacy_composer=composer,
        )

    @classmethod
    def from_v4(
        cls,
        composer: Any,
        selector: CandidateSelector | None = None,
        *,
        stages: Sequence[Reconstructor] = (),
        stage_ids: Sequence[str] = (),
    ) -> RuntimeProgram:
        selected_stages = tuple(stages)
        if not selected_stages:
            selected_stages = tuple(
                ComposerReconstructor(composer, stage_id)
                for stage_id in (stage_ids or ("compound",))
            )
        return cls(
            selected_stages,
            selector,
            bool(composer.recursive_components),
            int(composer.max_recursive_depth),
            int(composer.max_states),
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
        runtime_context = {
            "base_context": context,
            "literals": literals,
            "membership": membership,
            "prefix_index": prefix_index,
            "resolver": resolver,
        }
        candidates: list[ReconstructionCandidate] = []
        for reconstructor in self.reconstructors:
            candidates.extend(reconstructor.candidates(word, runtime_context))
        if not candidates:
            return None
        if self.selector is None:
            return candidates[0].pronunciation
        features = {
            "word_length": len(word),
            "candidate_count": len(candidates),
            "stage_ids": tuple(sorted({item.stage_id for item in candidates})),
        }
        selected = self.selector.choose(features, tuple(candidates))
        return selected.pronunciation if selected is not None else None

    def as_dict(self) -> dict[str, object]:
        return {
            "version": "1",
            "recursive_components": self.recursive_components,
            "max_recursive_depth": self.max_recursive_depth,
            "max_states": self.max_states,
            "reconstructors": [dict(item.as_dict()) for item in self.reconstructors],
            "selector": self.selector.as_dict()
            if self.selector is not None and hasattr(self.selector, "as_dict")
            else None,
            "selector_id": getattr(self.selector, "selector_id", None),
        }

    def serialize_sections(self) -> Mapping[str, bytes]:
        sections: dict[str, bytes] = {
            "runtime-program.json": json.dumps(
                self.as_dict(), sort_keys=True, separators=(",", ":")
            ).encode()
        }
        for reconstructor in self.reconstructors:
            sections.update(reconstructor.serialize_sections())
        return sections


__all__ = [
    "CandidateSelector",
    "ComposerReconstructor",
    "OverlayMapping",
    "ReconstructionCandidate",
    "Reconstructor",
    "ResolvedValues",
    "RuntimeProgram",
]
