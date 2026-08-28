"""Typed record encoding and independently compressed V5 record blocks."""

from __future__ import annotations

import struct
import zlib
from collections.abc import Mapping, Sequence
from itertools import pairwise

from .value import WORD_ONLY, LexiconValue, TaggedValue

WORD_ONLY_TYPE = 0
NULL_TYPE = 1
STRING_TYPE = 2
STRING_LIST_TYPE = 3
TAG_MAP_TYPE = 4


def encode_varint(value: int) -> bytes:
    if value < 0:
        raise ValueError("varints cannot encode negative values")
    output = bytearray()
    while value >= 0x80:
        output.append((value & 0x7F) | 0x80)
        value >>= 7
    output.append(value)
    return bytes(output)


def decode_varint(data: memoryview, position: int, end: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while position < end and shift <= 63:
        byte = data[position]
        position += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, position
        shift += 7
    raise ValueError("invalid or truncated record varint")


def _text(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return encode_varint(len(encoded)) + encoded


def _read_text(data: memoryview, position: int, end: int) -> tuple[str, int]:
    length, position = decode_varint(data, position, end)
    stop = position + length
    if stop > end:
        raise ValueError("truncated record string")
    try:
        return bytes(data[position:stop]).decode("utf-8"), stop
    except UnicodeDecodeError as exc:
        raise ValueError("invalid UTF-8 record string") from exc


def _encode_selector(value: str | None | tuple[str, ...]) -> bytes:
    if value is None:
        return bytes((NULL_TYPE,))
    if isinstance(value, str):
        return bytes((STRING_TYPE,)) + _text(value)
    return (
        bytes((STRING_LIST_TYPE,))
        + encode_varint(len(value))
        + b"".join(_text(item) for item in value)
    )


def _decode_selector(data: memoryview, position: int, end: int):
    if position >= end:
        raise ValueError("truncated selector payload")
    kind = data[position]
    position += 1
    if kind == NULL_TYPE:
        return None, position
    if kind == STRING_TYPE:
        return _read_text(data, position, end)
    if kind == STRING_LIST_TYPE:
        count, position = decode_varint(data, position, end)
        values = []
        for _ in range(count):
            value, position = _read_text(data, position, end)
            values.append(value)
        return tuple(values), position
    raise ValueError(f"invalid selector type: {kind}")


def encode_record(value: LexiconValue, tag_ids: Mapping[str, int]) -> bytes:
    if value is WORD_ONLY:
        return bytes((WORD_ONLY_TYPE,))
    if isinstance(value, str):
        return bytes((STRING_TYPE,)) + _text(value)
    if isinstance(value, tuple):
        return (
            bytes((STRING_LIST_TYPE,))
            + encode_varint(len(value))
            + b"".join(_text(item) for item in value)
        )
    if isinstance(value, TaggedValue):
        output = bytearray((TAG_MAP_TYPE,))
        output.extend(encode_varint(len(value.items)))
        for tag, selector in value.items:
            try:
                tag_id = tag_ids[tag]
            except KeyError as exc:
                raise ValueError(f"tag is missing from tag table: {tag!r}") from exc
            output.extend(encode_varint(tag_id))
            output.extend(_encode_selector(selector))
        return bytes(output)
    raise TypeError(f"unsupported lexicon value: {value!r}")


def decode_record(data: bytes | memoryview, tag_names: Sequence[str]) -> LexiconValue:
    view = memoryview(data)
    if not view:
        raise ValueError("empty record")
    value, position = _decode_record(view, 0, len(view), tag_names)
    if position != len(view):
        raise ValueError("trailing bytes in record")
    return value


def _decode_record(data: memoryview, position: int, end: int, tag_names: Sequence[str]):
    if position >= end:
        raise ValueError("truncated record")
    kind = data[position]
    position += 1
    if kind == WORD_ONLY_TYPE:
        return WORD_ONLY, position
    if kind == NULL_TYPE:
        return None, position
    if kind == STRING_TYPE:
        return _read_text(data, position, end)
    if kind == STRING_LIST_TYPE:
        count, position = decode_varint(data, position, end)
        values = []
        for _ in range(count):
            value, position = _read_text(data, position, end)
            values.append(value)
        return tuple(values), position
    if kind == TAG_MAP_TYPE:
        count, position = decode_varint(data, position, end)
        pairs = []
        for _ in range(count):
            tag_id, position = decode_varint(data, position, end)
            if tag_id >= len(tag_names):
                raise ValueError(f"unknown tag id: {tag_id}")
            selector, position = _decode_selector(data, position, end)
            pairs.append((tag_names[tag_id], selector))
        return TaggedValue(tuple(pairs)), position
    raise ValueError(f"invalid record type: {kind}")


def encode_record_block(values: Sequence[LexiconValue], tag_ids: Mapping[str, int]) -> bytes:
    records = [encode_record(value, tag_ids) for value in values]
    offsets = [0]
    payload = bytearray()
    for record in records:
        payload.extend(record)
        offsets.append(len(payload))
    return (
        struct.pack(">I", len(records))
        + b"".join(struct.pack(">I", offset) for offset in offsets)
        + bytes(payload)
    )


def decode_record_block(
    data: bytes | memoryview, tag_names: Sequence[str]
) -> tuple[LexiconValue, ...]:
    view = memoryview(data)
    if len(view) < 4:
        raise ValueError("truncated record block")
    count = struct.unpack_from(">I", view)[0]
    table_end = 4 + 4 * (count + 1)
    if table_end > len(view):
        raise ValueError("truncated record block offsets")
    offsets = [struct.unpack_from(">I", view, 4 + index * 4)[0] for index in range(count + 1)]
    if offsets[0] != 0 or any(left > right for left, right in pairwise(offsets)):
        raise ValueError("invalid record block offsets")
    payload = table_end
    if payload + offsets[-1] != len(view):
        raise ValueError("record block size mismatch")
    return tuple(
        decode_record(view[payload + offsets[index] : payload + offsets[index + 1]], tag_names)
        for index in range(count)
    )


def compress_block(raw: bytes, codec: str = "zlib", level: int = 9) -> bytes:
    if codec == "none":
        return raw
    if codec == "zlib":
        return zlib.compress(raw, level)
    raise ValueError(f"unsupported record codec: {codec!r}")


def decompress_block(stored: bytes | memoryview, codec: str, raw_size: int) -> bytes:
    if codec == "none":
        raw = bytes(stored)
    elif codec == "zlib":
        try:
            raw = zlib.decompress(stored)
        except zlib.error as exc:
            raise ValueError("invalid compressed record block") from exc
    else:
        raise ValueError(f"unsupported record codec: {codec!r}")
    if len(raw) != raw_size:
        raise ValueError("record block raw size mismatch")
    return raw


def encode_tags(tags: Sequence[str]) -> bytes:
    output = bytearray(b"TAG1" + struct.pack(">I", len(tags)))
    for tag in tags:
        output.extend(_text(tag))
    return bytes(output)


def decode_tags(data: bytes | memoryview) -> tuple[str, ...]:
    view = memoryview(data)
    if len(view) < 8 or bytes(view[:4]) != b"TAG1":
        raise ValueError("invalid tag table")
    count = struct.unpack_from(">I", view, 4)[0]
    tags = []
    position = 8
    for _ in range(count):
        tag, position = _read_text(view, position, len(view))
        tags.append(tag)
    if position != len(view) or len(set(tags)) != len(tags):
        raise ValueError("invalid tag table contents")
    return tuple(tags)
