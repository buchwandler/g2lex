"""Mmap-friendly front-coded UTF-8 key index for G2Lex v1."""

from __future__ import annotations

import struct
from collections.abc import Iterator, Sequence

_MAGIC = b"FCI1"
_HEADER = struct.Struct(">4sIII")


def _varint(value: int) -> bytes:
    output = bytearray()
    while value >= 0x80:
        output.append((value & 0x7F) | 0x80)
        value >>= 7
    output.append(value)
    return bytes(output)


def _read_varint(view: memoryview, position: int, end: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while position < end and shift <= 63:
        byte = view[position]
        position += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, position
        shift += 7
    raise ValueError("invalid or truncated key-index varint")


def _common_prefix(left: bytes, right: bytes) -> int:
    length = min(len(left), len(right))
    index = 0
    while index < length and left[index] == right[index]:
        index += 1
    return index


class FrontCodedKeyIndex:
    """Sorted key index that materializes only keys in the requested block."""

    backend_id = "front-coded-v1"

    def __init__(self, data: bytes | bytearray | memoryview):
        self._view = memoryview(data)
        if len(self._view) < _HEADER.size:
            raise ValueError("truncated front-coded key index")
        magic, self.block_entries, self.key_count, self.block_count = _HEADER.unpack_from(
            self._view
        )
        if (
            magic != _MAGIC
            or not self.block_entries
            or self.block_count != (self.key_count + self.block_entries - 1) // self.block_entries
        ):
            raise ValueError("invalid front-coded key index header")
        self._offset_table = _HEADER.size
        self._body = self._offset_table + 4 * (self.block_count + 1)
        if self._body > len(self._view):
            raise ValueError("truncated front-coded key-index offsets")
        self._body_end = len(self._view)
        previous = 0
        for index in range(self.block_count + 1):
            offset = struct.unpack_from(">I", self._view, self._offset_table + index * 4)[0]
            if offset < previous or self._body + offset > self._body_end:
                raise ValueError("invalid front-coded key-index offset")
            previous = offset

    @classmethod
    def encode(cls, keys: Sequence[str], block_entries: int = 32) -> bytes:
        ordered = sorted(keys, key=lambda item: item.encode("utf-8"))
        if len(set(ordered)) != len(ordered):
            raise ValueError("duplicate lexicon key")
        if block_entries <= 0:
            raise ValueError("block_entries must be positive")
        block_count = (len(ordered) + block_entries - 1) // block_entries
        body = bytearray()
        offsets = [0]
        for block_start in range(0, len(ordered), block_entries):
            previous = b""
            for offset, key in enumerate(ordered[block_start : block_start + block_entries]):
                encoded = key.encode("utf-8")
                prefix = 0 if offset == 0 else _common_prefix(previous, encoded)
                suffix = encoded[prefix:]
                body.extend(_varint(prefix))
                body.extend(_varint(len(suffix)))
                body.extend(suffix)
                previous = encoded
            offsets.append(len(body))
        header = _HEADER.pack(_MAGIC, block_entries, len(ordered), block_count)
        return header + b"".join(struct.pack(">I", offset) for offset in offsets) + body

    def _offset(self, block: int) -> tuple[int, int]:
        start = struct.unpack_from(">I", self._view, self._offset_table + block * 4)[0]
        end = struct.unpack_from(">I", self._view, self._offset_table + (block + 1) * 4)[0]
        return self._body + start, self._body + end

    def _decode_block(self, block: int) -> Iterator[tuple[str, int]]:
        start, end = self._offset(block)
        position = start
        previous = b""
        first_ordinal = block * self.block_entries
        for local in range(min(self.block_entries, self.key_count - first_ordinal)):
            prefix, position = _read_varint(self._view, position, end)
            suffix_length, position = _read_varint(self._view, position, end)
            suffix_end = position + suffix_length
            if prefix > len(previous) or suffix_end > end:
                raise ValueError("truncated front-coded key")
            encoded = previous[:prefix] + bytes(self._view[position:suffix_end])
            position = suffix_end
            try:
                key = encoded.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("invalid UTF-8 key") from exc
            yield key, first_ordinal + local
            previous = encoded
        if position != end:
            raise ValueError("trailing bytes in front-coded key block")

    def first_keys(self) -> Iterator[str]:
        for block in range(self.block_count):
            yield next(self._decode_block(block))[0]

    def find(self, key: str) -> int | None:
        if not isinstance(key, str) or not self.key_count:
            return None
        low, high = 0, self.block_count
        while low < high:
            middle = (low + high) // 2
            first = next(self._decode_block(middle))[0]
            if first <= key:
                low = middle + 1
            else:
                high = middle
        block = max(0, low - 1)
        for candidate, ordinal in self._decode_block(block):
            if candidate == key:
                return ordinal
            if candidate > key:
                return None
        return None

    def key_at(self, ordinal: int) -> str:
        if ordinal < 0 or ordinal >= self.key_count:
            raise IndexError(ordinal)
        block = ordinal // self.block_entries
        for key, current in self._decode_block(block):
            if current == ordinal:
                return key
        raise ValueError("key index block is inconsistent")

    def __iter__(self) -> Iterator[str]:
        for block in range(self.block_count):
            for key, _ in self._decode_block(block):
                yield key

    def __len__(self) -> int:
        return self.key_count
