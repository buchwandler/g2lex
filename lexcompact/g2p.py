"""Compact categorical CART-like grapheme to pronunciation model."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping

from .runtime import ReconstructionCandidate
from .training.alignment import align


def _length_bucket(length: int) -> int:
    return min(length // 4, 15)


def feature_key(word: str, position: int, previous_output: str = "") -> tuple[str, ...]:
    def at(index: int) -> str:
        if index < 0:
            return "<BOS>"
        if index >= len(word):
            return "<EOS>"
        return word[index]

    return (
        at(position - 2), at(position - 1), at(position), at(position + 1), at(position + 2),
        "upper" if word[position].isupper() else "lower" if word[position].islower() else "other",
        str(_length_bucket(len(word))),
        str(min(7, position * 8 // max(1, len(word)))),
        previous_output[:1] or "<EMPTY>",
    )


@dataclass(frozen=True, slots=True)
class CARTModel:
    table: tuple[tuple[tuple[str, ...], str], ...]
    default_output: str = ""
    max_bytes: int = 1024 * 1024
    version: str = "cart-v1"

    def predict(self, word: str) -> str:
        mapping = dict(self.table)
        output: list[str] = []
        previous = ""
        for position in range(len(word)):
            chunk = mapping.get(feature_key(word, position, previous), self.default_output)
            output.append(chunk)
            previous = chunk
        return "".join(output)

    def as_dict(self) -> dict[str, object]:
        return {"version": self.version, "default_output": self.default_output, "max_bytes": self.max_bytes, "table": [[list(key), value] for key, value in self.table]}

    def serialize(self) -> bytes:
        return json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()

    @property
    def serialized_bytes(self) -> int:
        return len(self.serialize())

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "CARTModel":
        model = cls(tuple((tuple(key), str(output)) for key, output in value.get("table", ())), str(value.get("default_output", "")), int(value.get("max_bytes", 1024 * 1024)), str(value.get("version", "cart-v1")))
        if model.serialized_bytes > model.max_bytes:
            raise ValueError("CART model exceeds byte budget")
        return model

    @classmethod
    def deserialize(cls, data: bytes) -> "CARTModel":
        return cls.from_dict(json.loads(data))


def train_cart(
    pairs: Iterable[tuple[str, str]],
    *,
    max_output_chunk_length: int = 4,
    max_bytes: int = 1024 * 1024,
) -> CARTModel:
    counts: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    all_outputs: Counter[str] = Counter()
    for spelling, pronunciation in pairs:
        previous = ""
        for position, (_, chunk) in enumerate(align(spelling, pronunciation, max_output_chunk_length=max_output_chunk_length)):
            key = feature_key(spelling, position, previous)
            counts[key][chunk] += 1
            all_outputs[chunk] += 1
            previous = chunk
    default = all_outputs.most_common(1)[0][0] if all_outputs else ""
    rows = [(key, values.most_common(1)[0][0]) for key, values in counts.items()]
    rows.sort(key=lambda item: item[0])
    model = CARTModel(tuple(rows), default, max_bytes)
    while model.serialized_bytes > max_bytes and rows:
        rows.pop()
        model = CARTModel(tuple(rows), default, max_bytes)
    if model.serialized_bytes > max_bytes:
        raise ValueError("CART model budget is too small for its default output")
    return model


class CARTReconstructor:
    stage_id = "cart"
    version = "1"

    def __init__(self, model: CARTModel) -> None:
        self.model = model

    def candidates(self, word: str, context: object = None) -> tuple[ReconstructionCandidate, ...]:
        return (ReconstructionCandidate(self.stage_id, (self.model.predict(word),), score=0, analysis_kind="cart"),)

    def as_dict(self):
        return {"stage_id": self.stage_id, "version": self.version, "model": self.model.as_dict()}

    def serialize_sections(self):
        return {"reconstructor.cart": self.model.serialize()}


__all__ = ["CARTModel", "CARTReconstructor", "feature_key", "train_cart"]
