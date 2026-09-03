"""Lazy mappings for virtual aliases and explicit raw-record layers."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from types import TracebackType
from typing import Any, cast

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
            return cast(LexiconValue, value)
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

    def __bool__(self) -> bool:
        """Return raw-mapping emptiness without enumerating aliases."""
        return bool(self.raw)

    def __len__(self) -> int:
        return sum(1 for _ in self)

    def close(self) -> None:
        close = getattr(self.raw, "close", None)
        if close is not None:
            close()


_MISSING = object()


@dataclass(frozen=True, slots=True)
class LayerHit:
    """The value and provenance of the first layer containing a key."""

    value: LexiconValue
    name: str
    metadata: Mapping[str, object]
    index: int


@dataclass(frozen=True, slots=True)
class LexiconLayer:
    name: str
    lexicon: Mapping[str, LexiconValue]
    metadata: Mapping[str, object]


class LayeredLexicon(Mapping[str, LexiconValue]):
    """Layered mapping with first-layer precedence and deterministic iteration.

    Composite lookups and iteration raise ``ValueError`` after :meth:`close`,
    matching the lifecycle behavior of :class:`g2lex.Lexicon`.
    """

    def __init__(self, layers: tuple[LexiconLayer, ...] | list[LexiconLayer]):
        self.layers = tuple(layers)
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise ValueError("lexicon is closed")

    def get_hit(self, word: str) -> LayerHit | None:
        """Return the first layer containing ``word``, including false-like values."""
        self._ensure_open()
        for index, layer in enumerate(self.layers):
            if word in layer.lexicon:
                return LayerHit(layer.lexicon[word], layer.name, layer.metadata, index)
        return None

    def get_hit_candidates(self, candidates: Iterable[str]) -> LayerHit | None:
        """Return the first hit using layer-first, candidate-second precedence."""
        self._ensure_open()
        ordered: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate not in seen:
                seen.add(candidate)
                ordered.append(candidate)
        for index, layer in enumerate(self.layers):
            for candidate in ordered:
                if candidate in layer.lexicon:
                    return LayerHit(layer.lexicon[candidate], layer.name, layer.metadata, index)
        return None

    def get(self, word: str, default: Any = None) -> LexiconValue | Any:
        hit = self.get_hit(word)
        return default if hit is None else hit.value

    def __getitem__(self, word: str) -> LexiconValue:
        hit = self.get_hit(word)
        if hit is None:
            raise KeyError(word)
        return hit.value

    def __contains__(self, word: object) -> bool:
        self._ensure_open()
        return isinstance(word, str) and any(word in layer.lexicon for layer in self.layers)

    def __iter__(self) -> Iterator[str]:
        self._ensure_open()
        seen: set[str] = set()
        for layer in self.layers:
            for word in layer.lexicon:
                if word not in seen:
                    seen.add(word)
                    yield word

    def __len__(self) -> int:
        self._ensure_open()
        return sum(1 for _ in self)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        closed: set[int] = set()
        for layer in self.layers:
            mapping_id = id(layer.lexicon)
            if mapping_id in closed:
                continue
            close = getattr(layer.lexicon, "close", None)
            if close is not None:
                close()
            closed.add(mapping_id)

    def __enter__(self) -> LayeredLexicon:  # noqa: PYI034
        self._ensure_open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
