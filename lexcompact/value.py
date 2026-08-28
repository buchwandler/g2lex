"""Typed, source-neutral lexicon values used by the V5 format."""

from __future__ import annotations

import hashlib
import struct
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import TypeAlias


class _Items(tuple[tuple[str, "SelectorValue"], ...]):
    """Tuple of selector pairs that also supports the usual ``items()`` call."""

    def __new__(
        cls, values: tuple[tuple[str, SelectorValue], ...] | list[tuple[str, SelectorValue]]
    ):
        return super().__new__(cls, values)

    def __call__(self) -> Iterator[tuple[str, SelectorValue]]:
        return iter(self)


SelectorValue: TypeAlias = str | None | tuple[str, ...]


@dataclass(frozen=True, slots=True, eq=False)
class TaggedValue(Mapping[str, SelectorValue]):
    """An immutable ordered selector map.

    ``items`` is deliberately an ordered tuple.  It is callable as well, so both
    ``value.items`` and the normal mapping spelling ``value.items()`` are useful.
    """

    items: tuple[tuple[str, SelectorValue], ...]

    def __post_init__(self) -> None:
        pairs: list[tuple[str, SelectorValue]] = []
        seen: set[str] = set()
        for pair in self.items:
            if not isinstance(pair, tuple) or len(pair) != 2:
                raise TypeError("tagged items must be (tag, value) pairs")
            tag, value = pair
            if not isinstance(tag, str):
                raise TypeError("tag names must be strings")
            if tag in seen:
                raise ValueError(f"duplicate selector tag: {tag!r}")
            seen.add(tag)
            validate_selector_value(value)
            pairs.append((tag, value))
        object.__setattr__(self, "items", _Items(tuple(pairs)))

    def __getitem__(self, tag: str) -> SelectorValue:
        for key, value in self.items:
            if key == tag:
                return value
        raise KeyError(tag)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TaggedValue):
            return self.items == other.items
        if isinstance(other, Mapping):
            return dict(self.items) == dict(other.items())
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.items)

    @classmethod
    def from_mapping(cls, value: Mapping[str, SelectorValue]) -> TaggedValue:
        return cls(tuple(value.items()))


def validate_selector_value(value: object) -> None:
    if value is None or isinstance(value, str):
        return
    if isinstance(value, tuple) and all(isinstance(item, str) for item in value):
        return
    raise TypeError("selector values must be strings, null, or tuples of strings")


class _WordOnly:
    __slots__ = ()

    def __repr__(self) -> str:
        return "WORD_ONLY"

    def __reduce__(self) -> tuple[object, tuple[()]]:
        return (_word_only, ())


WORD_ONLY = _WordOnly()
WordOnly = _WordOnly
LexiconValue: TypeAlias = str | tuple[str, ...] | TaggedValue | _WordOnly


def _word_only() -> _WordOnly:
    return WORD_ONLY


def validate_value(value: object) -> None:
    if isinstance(value, str) or value is WORD_ONLY:
        return
    if isinstance(value, tuple) and all(isinstance(item, str) for item in value):
        return
    if isinstance(value, TaggedValue):
        return
    raise TypeError("lexicon values must be strings, string tuples, TaggedValue, or WORD_ONLY")


def _put_bytes(buffer: bytearray, value: bytes) -> None:
    buffer.extend(struct.pack(">I", len(value)))
    buffer.extend(value)


def _put_text(buffer: bytearray, value: str) -> None:
    _put_bytes(buffer, value.encode("utf-8"))


def _canonical_value(buffer: bytearray, value: LexiconValue) -> None:
    validate_value(value)
    if value is WORD_ONLY:
        buffer.append(0)
    elif isinstance(value, str):
        buffer.append(1)
        _put_text(buffer, value)
    elif isinstance(value, tuple):
        buffer.append(2)
        buffer.extend(struct.pack(">I", len(value)))
        for item in value:
            _put_text(buffer, item)
    else:
        buffer.append(3)
        buffer.extend(struct.pack(">I", len(value.items)))
        for tag, selector in value.items:
            _put_text(buffer, tag)
            if selector is None:
                buffer.append(0)
            elif isinstance(selector, str):
                buffer.append(1)
                _put_text(buffer, selector)
            else:
                buffer.append(2)
                buffer.extend(struct.pack(">I", len(selector)))
                for item in selector:
                    _put_text(buffer, item)


def canonical_bytes(entries: Mapping[str, LexiconValue]) -> bytes:
    """Return an unambiguous deterministic representation of logical entries."""

    output = bytearray(b"LXC5-LOGICAL-1")
    for word in sorted(entries):
        if not isinstance(word, str):
            raise TypeError("lexicon keys must be strings")
        _put_text(output, word)
        _canonical_value(output, entries[word])
    return bytes(output)


def logical_sha256(entries: Mapping[str, LexiconValue]) -> str:
    return hashlib.sha256(canonical_bytes(entries)).hexdigest()


def as_plain_value(value: LexiconValue) -> object:
    """Materialize a typed value into ordinary JSON-compatible Python objects."""

    if value is WORD_ONLY:
        return WORD_ONLY
    if isinstance(value, TaggedValue):
        return {tag: as_plain_selector(selector) for tag, selector in value.items}
    return value


def as_plain_selector(value: SelectorValue) -> object:
    if isinstance(value, tuple):
        return list(value)
    return value
