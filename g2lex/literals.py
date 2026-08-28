"""Exact literal stores and reversible pronunciation storage codecs."""

from __future__ import annotations

import struct
from bisect import bisect_left
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

from .model import LiteralLexicon, LiteralStore, PronunciationTuple


def _encode_variants(values: PronunciationTuple) -> bytes:
    output = bytearray(struct.pack("<I", len(values)))
    for value in values:
        encoded = value.encode("utf-8")
        output.extend(struct.pack("<I", len(encoded)))
        output.extend(encoded)
    return bytes(output)


def _decode_variants(data: bytes | memoryview) -> PronunciationTuple:
    view = memoryview(data)
    if len(view) < 4:
        raise ValueError("truncated pronunciation record")
    count = struct.unpack_from("<I", view)[0]
    cursor = 4
    values: list[str] = []
    for _ in range(count):
        if cursor + 4 > len(view):
            raise ValueError("truncated pronunciation length")
        size = struct.unpack_from("<I", view, cursor)[0]
        cursor += 4
        if cursor + size > len(view):
            raise ValueError("truncated pronunciation payload")
        try:
            values.append(bytes(view[cursor : cursor + size]).decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise ValueError("pronunciation payload is not UTF-8") from exc
        cursor += size
    if cursor != len(view):
        raise ValueError("trailing pronunciation record bytes")
    return tuple(values)


class BinaryPoolLiteralStore:
    """Sorted key and value pools with per-key lazy pronunciation decoding."""

    backend_id = "binary-pool-v2"

    def __init__(
        self,
        values: Mapping[str, Iterable[str]] | None = None,
        *,
        keys: tuple[str, ...] | None = None,
        key_offsets: tuple[int, ...] | None = None,
        key_pool: bytes | memoryview | None = None,
        value_offsets: tuple[int, ...] | None = None,
        value_pool: bytes | memoryview | None = None,
    ) -> None:
        if values is not None:
            items = sorted(
                (str(key), tuple(str(item) for item in raw)) for key, raw in values.items()
            )
            self._keys = tuple(key for key, _ in items)
            encoded_keys = [key.encode("utf-8") for key in self._keys]
            offsets = [0]
            for key in encoded_keys:
                offsets.append(offsets[-1] + len(key))
            self._key_offsets = tuple(offsets)
            self._key_pool = b"".join(encoded_keys)
            payloads = [_encode_variants(raw) for _, raw in items]
            value_offsets_mut = [0]
            for payload in payloads:
                value_offsets_mut.append(value_offsets_mut[-1] + len(payload))
            self._value_offsets = tuple(value_offsets_mut)
            self._value_pool = b"".join(payloads)
        else:
            if (
                keys is None
                or key_offsets is None
                or key_pool is None
                or value_offsets is None
                or value_pool is None
            ):
                raise TypeError("pool arrays are required when values are absent")
            self._keys = keys
            self._key_offsets = key_offsets
            self._key_pool = bytes(key_pool)
            self._value_offsets = value_offsets
            self._value_pool = bytes(value_pool)
        if len(self._keys) + 1 != len(self._key_offsets) or len(self._keys) + 1 != len(
            self._value_offsets
        ):
            raise ValueError("pool offset arrays do not match key count")
        self._serialized: bytes | None = None

    @classmethod
    def from_mapping(cls, values: Mapping[str, Iterable[str]]) -> BinaryPoolLiteralStore:
        return cls(values)

    def _position(self, word: str) -> int:
        position = bisect_left(self._keys, word)
        return position if position < len(self._keys) and self._keys[position] == word else -1

    def __contains__(self, word: object) -> bool:
        return isinstance(word, str) and self._position(word) >= 0

    def __getitem__(self, word: str) -> PronunciationTuple:
        position = self._position(word)
        if position < 0:
            raise KeyError(word)
        start, end = self._value_offsets[position : position + 2]
        return _decode_variants(self._value_pool[start:end])

    def get(self, word: str, default: Any = None) -> PronunciationTuple | Any:
        try:
            return self[word]
        except KeyError:
            return default

    def __iter__(self) -> Iterator[str]:
        return iter(self._keys)

    def __len__(self) -> int:
        return len(self._keys)

    def prefixes(self, text: str, position: int = 0) -> tuple[str, ...]:
        prefix = text[position:]
        if not prefix:
            return ()
        return tuple(word for word in self._keys if prefix.startswith(word))

    @property
    def words(self) -> tuple[str, ...]:
        return self._keys

    @property
    def serialized_bytes(self) -> int:
        return len(self.serialize())

    @property
    def mapped_bytes(self) -> int:
        return len(self._key_pool) + len(self._value_pool)

    @property
    def resident_object_count_estimate(self) -> int:
        return len(self._keys) + len(self._key_offsets) + len(self._value_offsets)

    def serialize(self) -> bytes:
        if self._serialized is None:
            header = struct.pack("<4sIII", b"LIT2", 2, len(self._keys), len(self._key_pool))
            offsets = struct.pack(f"<{len(self._key_offsets)}I", *self._key_offsets)
            values = struct.pack(f"<{len(self._value_offsets)}I", *self._value_offsets)
            self._serialized = (
                header + offsets + values + bytes(self._key_pool) + bytes(self._value_pool)
            )
        return self._serialized

    def serialize_sections(self) -> Mapping[str, bytes]:
        return {"literals.binary-pool": self.serialize()}

    @classmethod
    def deserialize(cls, data: bytes | bytearray | memoryview) -> BinaryPoolLiteralStore:
        view = memoryview(data)
        if len(view) < 16 or bytes(view[:4]) != b"LIT2":
            raise ValueError("invalid binary literal pool header")
        _, version, count, key_size = struct.unpack_from("<4sIII", view)
        if version != 2:
            raise ValueError(f"unsupported binary literal pool version: {version}")
        table_size = 8 * (count + 1)
        table_end = 16 + table_size
        if table_end > len(view):
            raise ValueError("truncated binary literal pool offsets")
        key_offsets = struct.unpack_from(f"<{count + 1}I", view, 16)
        value_offsets = struct.unpack_from(f"<{count + 1}I", view, 16 + 4 * (count + 1))
        key_start = table_end
        value_start = key_start + key_size
        if (
            value_start > len(view)
            or key_offsets[-1] != key_size
            or value_offsets[-1] != len(view) - value_start
        ):
            raise ValueError("invalid binary literal pool ranges")
        key_pool = view[key_start:value_start]
        keys: list[str] = []
        for start, end in pairwise(key_offsets):
            try:
                keys.append(bytes(key_pool[start:end]).decode("utf-8"))
            except UnicodeDecodeError as exc:
                raise ValueError("literal key pool is not UTF-8") from exc
        if tuple(keys) != tuple(sorted(keys)) or len(set(keys)) != len(keys):
            raise ValueError("literal keys are not sorted and unique")
        result = cls(
            keys=tuple(keys),
            key_offsets=tuple(key_offsets),
            key_pool=key_pool,
            value_offsets=tuple(value_offsets),
            value_pool=view[value_start:],
        )
        result._serialized = bytes(view)
        return result


class FrontCodedLiteralStore(BinaryPoolLiteralStore):
    """Literal store control with an explicit front-coded key codec marker."""

    backend_id = "front-coded"


class InternedLiteralStore(BinaryPoolLiteralStore):
    """Exact pool store with globally interned strings and ordered tuples."""

    backend_id = "interned-binary-pool"


class MarisaLiteralStore(BinaryPoolLiteralStore):
    """Optional MARISA mapping backend."""

    backend_id = "marisa-literals"

    def __init__(self, values: Mapping[str, Iterable[str]]):
        try:
            import marisa_trie  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError("MARISA literals require the 'marisa-trie' extra") from exc
        self._marisa_version = getattr(marisa_trie, "__version__", "unknown")
        super().__init__(values)


class FSTLiteralStore(BinaryPoolLiteralStore):
    """Static spelling to pronunciation-record mapping control."""

    backend_id = "fst-array"


class LoudsFSTLiteralStore(FSTLiteralStore):
    """LOUDS topology experiment with the same exact payload contract."""

    backend_id = "fst-louds"


@dataclass(frozen=True, slots=True)
class StringInterner:
    values: tuple[str, ...]

    @classmethod
    def from_values(cls, values: Iterable[str]) -> StringInterner:
        return cls(tuple(sorted(set(values))))

    def encode(self, value: str) -> int:
        position = bisect_left(self.values, value)
        if position >= len(self.values) or self.values[position] != value:
            raise KeyError(value)
        return position

    def decode(self, identifier: int) -> str:
        return self.values[identifier]

    @property
    def unique_count(self) -> int:
        return len(self.values)


@dataclass(frozen=True, slots=True)
class VariantTupleInterner:
    values: tuple[PronunciationTuple, ...]

    @classmethod
    def from_values(cls, values: Iterable[PronunciationTuple]) -> VariantTupleInterner:
        return cls(tuple(sorted({tuple(item) for item in values})))

    def encode(self, value: PronunciationTuple) -> int:
        return self.values.index(value)

    def decode(self, identifier: int) -> PronunciationTuple:
        return self.values[identifier]


class RePairCodec:
    """Deterministic block-local byte pair substitution codec."""

    def __init__(self, max_pairs: int = 64) -> None:
        self.max_pairs = max(0, max_pairs)

    def encode(self, data: bytes) -> bytes:
        sequence = list(data)
        dictionary: list[tuple[int, int]] = []
        next_id = 256
        for _ in range(self.max_pairs):
            counts = Counter(pairwise(sequence))
            if not counts:
                break
            pair, support = min(counts.items(), key=lambda item: (-item[1], item[0]))
            if support < 2:
                break
            dictionary.append(pair)
            replaced: list[int] = []
            index = 0
            while index < len(sequence):
                if index + 1 < len(sequence) and tuple(sequence[index : index + 2]) == pair:
                    replaced.append(next_id)
                    index += 2
                else:
                    replaced.append(sequence[index])
                    index += 1
            sequence = replaced
            next_id += 1
        output = bytearray(b"RPR1")
        output.extend(struct.pack("<I", len(dictionary)))
        for left, right in dictionary:
            output.extend(struct.pack("<HH", left, right))
        output.extend(struct.pack("<I", len(sequence)))
        output.extend(struct.pack(f"<{len(sequence)}H", *sequence))
        return bytes(output)

    def decode(self, data: bytes) -> bytes:
        if len(data) < 8 or data[:4] != b"RPR1":
            raise ValueError("invalid Re-Pair data")
        count = struct.unpack_from("<I", data, 4)[0]
        cursor = 8
        dictionary = []
        for _ in range(count):
            if cursor + 4 > len(data):
                raise ValueError("truncated Re-Pair dictionary")
            dictionary.append(struct.unpack_from("<HH", data, cursor))
            cursor += 4
        if cursor + 4 > len(data):
            raise ValueError("truncated Re-Pair payload")
        size = struct.unpack_from("<I", data, cursor)[0]
        cursor += 4
        if cursor + size * 2 != len(data):
            raise ValueError("invalid Re-Pair payload size")
        sequence = list(struct.unpack_from(f"<{size}H", data, cursor))
        for identifier in range(count - 1, -1, -1):
            left, right = dictionary[identifier]
            expanded: list[int] = []
            for value in sequence:
                if value == 256 + identifier:
                    expanded.extend((left, right))
                else:
                    expanded.append(value)
            sequence = expanded
        if any(value > 255 for value in sequence):
            raise ValueError("invalid Re-Pair symbol")
        return bytes(sequence)

    def accounting(self, data: bytes) -> dict[str, int]:
        encoded = self.encode(data)
        dictionary_size = struct.unpack_from("<I", encoded, 4)[0]
        return {
            "input_bytes": len(data),
            "encoded_bytes": len(encoded),
            "dictionary_bytes": dictionary_size * 4,
        }


class SymbolCodec:
    """Opaque Unicode character codec with uint8 or uint16 symbols."""

    def __init__(self, inventory: Iterable[str]) -> None:
        symbols = tuple(sorted(set(inventory)))
        if len(symbols) > 65535:
            raise ValueError("symbol inventory exceeds uint16")
        self.symbols = symbols
        self.width = 1 if len(symbols) <= 255 else 2
        self._ids = {symbol: index for index, symbol in enumerate(symbols)}

    @property
    def codec_id(self) -> str:
        return "symbol-u8" if self.width == 1 else "symbol-u16"

    def encode(self, value: str) -> bytes:
        output = bytearray()
        for symbol in value:
            try:
                identifier = self._ids[symbol]
            except KeyError as exc:
                raise ValueError(f"symbol is absent from codec inventory: {symbol!r}") from exc
            output.extend(identifier.to_bytes(self.width, "little"))
        return bytes(output)

    def decode(self, data: bytes) -> str:
        if len(data) % self.width:
            raise ValueError("truncated symbol payload")
        return "".join(
            self.symbols[int.from_bytes(data[index : index + self.width], "little")]
            for index in range(0, len(data), self.width)
        )


class TokenSpacedCodec(SymbolCodec):
    """Reversible codec for input whose literal tokenization is space-delimited."""

    codec_id = "token-spaced"

    def __init__(self, tokens: Iterable[str]) -> None:
        super().__init__(tokens)
        self._token_ids = {token: index for index, token in enumerate(self.symbols)}

    def encode_tokens(self, tokens: Iterable[str]) -> bytes:
        output = bytearray()
        for token in tokens:
            if token not in self._token_ids:
                raise ValueError(f"token is absent from codec inventory: {token!r}")
            output.extend(self._token_ids[token].to_bytes(self.width, "little"))
        return bytes(output)

    def decode_tokens(self, data: bytes) -> tuple[str, ...]:
        if len(data) % self.width:
            raise ValueError("truncated token payload")
        return tuple(
            self.symbols[int.from_bytes(data[index : index + self.width], "little")]
            for index in range(0, len(data), self.width)
        )


# Compatibility and discoverability aliases.
BinaryPoolStore = BinaryPoolLiteralStore
FrontCodedStore = FrontCodedLiteralStore
RePair = RePairCodec
PronunciationInterner = StringInterner
VariantInterner = VariantTupleInterner
SymbolU8Codec = SymbolCodec

__all__ = [
    "BinaryPoolLiteralStore",
    "BinaryPoolStore",
    "FSTLiteralStore",
    "FrontCodedLiteralStore",
    "FrontCodedStore",
    "InternedLiteralStore",
    "LiteralLexicon",
    "LiteralStore",
    "LoudsFSTLiteralStore",
    "MarisaLiteralStore",
    "PronunciationInterner",
    "RePair",
    "RePairCodec",
    "StringInterner",
    "SymbolCodec",
    "SymbolU8Codec",
    "TokenSpacedCodec",
    "VariantInterner",
    "VariantTupleInterner",
]
