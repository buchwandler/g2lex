"""Lazy mappings for virtual aliases and explicit raw-record layers."""

from __future__ import annotations

import heapq
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from .value import LexiconValue


def _generated_alias(word: str) -> str | None:
    if len(word) < 2:
        return None
    if word == word.lower():
        return word.capitalize()
    if word == word.lower().capitalize():
        return word.lower()
    return None


class CaseAliasMapping(Mapping[str, LexiconValue]):
    """Expose the Kokoro capitalization expansion without storing aliases."""

    def __init__(self, raw: Mapping[str, LexiconValue]):
        self.raw = raw

    def _alias_owner(self, alias: str) -> str | None:
        candidates = []
        lower = alias.lower()
        if alias == lower.capitalize():
            candidates.append(lower)
        if alias == lower:
            candidates.append(alias.capitalize())
        for candidate in candidates:
            if (
                candidate != alias
                and candidate in self.raw
                and _generated_alias(candidate) == alias
            ):
                return candidate
        return None

    def __getitem__(self, word: str) -> LexiconValue:
        value = self.raw.get(word, _MISSING)
        if value is not _MISSING:
            return value
        owner = self._alias_owner(word)
        if owner is None:
            raise KeyError(word)
        return self.raw[owner]

    def get(self, word: str, default: Any = None) -> LexiconValue | Any:
        value = self.raw.get(word, _MISSING)
        if value is not _MISSING:
            return value
        owner = self._alias_owner(word)
        return default if owner is None else self.raw[owner]

    def __contains__(self, word: object) -> bool:
        if not isinstance(word, str):
            return False
        return word in self.raw or self._alias_owner(word) is not None

    def __iter__(self) -> Iterator[str]:
        for word in self.raw:
            yield word
        for word in self.raw:
            alias = _generated_alias(word)
            if (
                alias is not None
                and alias != word
                and alias not in self.raw
                and self._alias_owner(alias) == word
            ):
                yield alias

    def __len__(self) -> int:
        return sum(1 for _ in self)

    def close(self) -> None:
        close = getattr(self.raw, "close", None)
        if close is not None:
            close()


_MISSING = object()


@dataclass(frozen=True, slots=True)
class LexiconLayer:
    name: str
    lexicon: Mapping[str, LexiconValue]
    metadata: Mapping[str, object]


class LayeredLexicon(Mapping[str, LexiconValue]):
    """Resolve layers by raw record presence, never by selected values."""

    def __init__(self, layers: tuple[LexiconLayer, ...] | list[LexiconLayer]):
        self.layers = tuple(layers)

    def get(self, word: str, default: Any = None) -> LexiconValue | Any:
        for layer in self.layers:
            value = layer.lexicon.get(word, _MISSING)
            if value is not _MISSING:
                return value
        return default

    def __getitem__(self, word: str) -> LexiconValue:
        value = self.get(word, _MISSING)
        if value is _MISSING:
            raise KeyError(word)
        return value

    def __contains__(self, word: object) -> bool:
        return isinstance(word, str) and any(word in layer.lexicon for layer in self.layers)

    def __iter__(self) -> Iterator[str]:
        iterators = [iter(layer.lexicon) for layer in self.layers]
        heap: list[tuple[str, int]] = []
        for index, iterator in enumerate(iterators):
            try:
                heapq.heappush(heap, (next(iterator), index))
            except StopIteration:
                pass
        previous = _MISSING
        while heap:
            word, index = heapq.heappop(heap)
            if word != previous:
                yield word
                previous = word
            try:
                heapq.heappush(heap, (next(iterators[index]), index))
            except StopIteration:
                pass

    def __len__(self) -> int:
        return sum(1 for _ in self)

    def close(self) -> None:
        for layer in self.layers:
            close = getattr(layer.lexicon, "close", None)
            if close is not None:
                close()
