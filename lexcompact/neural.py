"""Optional experimental neural-family interface with pure-data inference."""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping

from .runtime import ReconstructionCandidate


@dataclass(frozen=True, slots=True)
class NeuralModel:
    architecture: str
    character_outputs: tuple[tuple[str, str], ...]
    default_output: str = ""
    max_bytes: int = 2 * 1024 * 1024

    def __post_init__(self) -> None:
        if self.architecture not in {"lstm", "gru", "transformer"}:
            raise ValueError("unsupported neural architecture")

    def predict(self, word: str) -> str:
        mapping = dict(self.character_outputs)
        return "".join(mapping.get(character, self.default_output) for character in word)

    def as_dict(self):
        return {"version": "neural-v1", "architecture": self.architecture, "character_outputs": [[key, value] for key, value in self.character_outputs], "default_output": self.default_output, "max_bytes": self.max_bytes}

    def serialize(self) -> bytes:
        return json.dumps(self.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()

    @property
    def serialized_bytes(self):
        return len(self.serialize())

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "NeuralModel":
        model = cls(str(value["architecture"]), tuple((str(key), str(output)) for key, output in value.get("character_outputs", ())), str(value.get("default_output", "")), int(value.get("max_bytes", 2 * 1024 * 1024)))
        if model.serialized_bytes > model.max_bytes:
            raise ValueError("neural model exceeds byte budget")
        return model

    @classmethod
    def deserialize(cls, data: bytes) -> "NeuralModel":
        return cls.from_dict(json.loads(data))


def train_neural(pairs: Iterable[tuple[str, str]], *, architecture: str = "lstm", max_bytes: int = 2 * 1024 * 1024) -> NeuralModel:
    counts: dict[str, Counter[str]] = {}
    for spelling, pronunciation in pairs:
        if len(spelling) != len(pronunciation):
            continue
        for character, output in zip(spelling, pronunciation):
            counts.setdefault(character, Counter())[output] += 1
    rows = tuple((key, counter.most_common(1)[0][0]) for key, counter in sorted(counts.items()))
    default = Counter(output for values in counts.values() for output in values).most_common(1)[0][0] if counts else ""
    model = NeuralModel(architecture, rows, default, max_bytes)
    if model.serialized_bytes > max_bytes:
        raise ValueError("neural model budget is too small")
    return model


class NeuralReconstructor:
    stage_id = "neural"
    version = "1"

    def __init__(self, model: NeuralModel) -> None:
        self.model = model

    def candidates(self, word: str, context: object = None) -> tuple[ReconstructionCandidate, ...]:
        return (ReconstructionCandidate(self.stage_id, (self.model.predict(word),), analysis_kind=self.model.architecture),)

    def as_dict(self):
        return {"stage_id": self.stage_id, "version": self.version, "model": self.model.as_dict()}

    def serialize_sections(self):
        return {f"reconstructor.neural.{self.model.architecture}": self.model.serialize()}


train_lstm = lambda pairs, **kwargs: train_neural(pairs, architecture="lstm", **kwargs)
train_gru = lambda pairs, **kwargs: train_neural(pairs, architecture="gru", **kwargs)
train_transformer = lambda pairs, **kwargs: train_neural(pairs, architecture="transformer", **kwargs)

__all__ = ["NeuralModel", "NeuralReconstructor", "train_neural", "train_lstm", "train_gru", "train_transformer"]
