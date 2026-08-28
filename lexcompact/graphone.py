"""Pure-data bounded graphone model and decoder."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .runtime import ReconstructionCandidate
from .training.alignment import align


@dataclass(frozen=True, slots=True)
class GraphoneModel:
    units: tuple[tuple[str, str], ...]
    order: int = 1
    max_graphemes_per_unit: int = 2
    max_pronunciation_codepoints_per_unit: int = 4
    beam_width: int = 8
    max_states: int = 10000
    max_bytes: int = 1024 * 1024

    def __post_init__(self) -> None:
        if self.order not in (1, 2, 3, 4):
            raise ValueError("graphone order must be between 1 and 4")
        if self.max_graphemes_per_unit < 1 or self.max_pronunciation_codepoints_per_unit < 0:
            raise ValueError("graphone unit limits are invalid")

    def predict(self, word: str) -> str:
        mapping = dict(self.units)
        output: list[str] = []
        position = 0
        states = 0
        while position < len(word):
            states += 1
            if states > self.max_states:
                raise RuntimeError("graphone state limit reached")
            chosen = None
            for size in range(min(self.max_graphemes_per_unit, len(word) - position), 0, -1):
                key = word[position : position + size]
                if key in mapping:
                    chosen = (size, mapping[key])
                    break
            if chosen is None:
                return ""
            size, pronunciation = chosen
            output.append(pronunciation)
            position += size
        return "".join(output)

    def as_dict(self) -> dict[str, object]:
        return {
            "version": "graphone-v1",
            "order": self.order,
            "max_graphemes_per_unit": self.max_graphemes_per_unit,
            "max_pronunciation_codepoints_per_unit": self.max_pronunciation_codepoints_per_unit,
            "beam_width": self.beam_width,
            "max_states": self.max_states,
            "max_bytes": self.max_bytes,
            "units": [[key, value] for key, value in self.units],
        }

    def serialize(self) -> bytes:
        return json.dumps(
            self.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()

    @property
    def serialized_bytes(self) -> int:
        return len(self.serialize())

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> GraphoneModel:
        model = cls(
            tuple((str(key), str(output)) for key, output in value.get("units", ())),
            int(value.get("order", 1)),
            int(value.get("max_graphemes_per_unit", 2)),
            int(value.get("max_pronunciation_codepoints_per_unit", 4)),
            int(value.get("beam_width", 8)),
            int(value.get("max_states", 10000)),
            int(value.get("max_bytes", 1024 * 1024)),
        )
        if model.serialized_bytes > model.max_bytes:
            raise ValueError("graphone model exceeds byte budget")
        return model

    @classmethod
    def deserialize(cls, data: bytes) -> GraphoneModel:
        return cls.from_dict(json.loads(data))


def train_graphone(
    pairs: Iterable[tuple[str, str]],
    *,
    order: int = 1,
    max_graphemes_per_unit: int = 2,
    max_pronunciation_codepoints_per_unit: int = 4,
    max_bytes: int = 1024 * 1024,
) -> GraphoneModel:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for spelling, pronunciation in pairs:
        for grapheme, output in align(
            spelling, pronunciation, max_output_chunk_length=max_pronunciation_codepoints_per_unit
        ):
            if len(grapheme) <= max_graphemes_per_unit:
                counts[grapheme][output] += 1
    units = [(key, counts[key].most_common(1)[0][0]) for key in counts]
    units.sort()
    model = GraphoneModel(
        tuple(units),
        order,
        max_graphemes_per_unit,
        max_pronunciation_codepoints_per_unit,
        max_bytes=max_bytes,
    )
    while model.serialized_bytes > max_bytes and units:
        units.pop()
        model = GraphoneModel(
            tuple(units),
            order,
            max_graphemes_per_unit,
            max_pronunciation_codepoints_per_unit,
            max_bytes=max_bytes,
        )
    if model.serialized_bytes > max_bytes:
        raise ValueError("graphone model budget is too small")
    return model


class GraphoneReconstructor:
    stage_id = "graphone"
    version = "1"

    def __init__(self, model: GraphoneModel) -> None:
        self.model = model

    def candidates(self, word: str, context: object = None) -> tuple[ReconstructionCandidate, ...]:
        prediction = self.model.predict(word)
        return (
            (
                ReconstructionCandidate(
                    self.stage_id, (prediction,), score=0, analysis_kind="graphone"
                ),
            )
            if prediction
            else ()
        )

    def as_dict(self):
        return {"stage_id": self.stage_id, "version": self.version, "model": self.model.as_dict()}

    def serialize_sections(self):
        return {f"reconstructor.graphone.{self.model.order}": self.model.serialize()}


__all__ = ["GraphoneModel", "GraphoneReconstructor", "train_graphone"]
