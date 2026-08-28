"""Deterministic indexed binary container used by Lexcompact V4 assets."""

from __future__ import annotations

import hashlib
import mmap
import struct
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAGIC = b"LXC4"
SCHEMA = 4
_HEADER = struct.Struct("<4sIIQ")
_ENTRY_HEAD = struct.Struct("<HQQQBI")
_HASH_SIZE = 32
_ALIGNMENT = 8


@dataclass(frozen=True, slots=True)
class Section:
    name: str
    data: memoryview
    codec: int = 0


class V4Container(Mapping[str, memoryview]):
    """Validated read-only view of an indexed V4 container."""

    def __init__(
        self, sections: Mapping[str, memoryview], *, schema: int = SCHEMA, owner: Any = None
    ):
        self._sections = dict(sections)
        self.schema = schema
        self._owner = owner

    def __getitem__(self, name: str) -> memoryview:
        return self._sections[name]

    def __iter__(self):
        return iter(self._sections)

    def __len__(self):
        return len(self._sections)

    @property
    def sections(self) -> tuple[Section, ...]:
        return tuple(Section(name, data) for name, data in self._sections.items())


def _align(value: int) -> int:
    return (value + _ALIGNMENT - 1) // _ALIGNMENT * _ALIGNMENT


def dumps(sections: Mapping[str, bytes | bytearray | memoryview], *, schema: int = SCHEMA) -> bytes:
    if schema != SCHEMA:
        raise ValueError(f"unsupported V4 schema: {schema}")
    names = tuple(sorted(sections))
    if any(not name or "/" in name or "\\" in name or name in {".", ".."} for name in names):
        raise ValueError("invalid V4 section name")
    output = bytearray(_HEADER.size)
    entries: list[tuple[str, int, int, int, int, bytes]] = []
    for name in names:
        start = _align(len(output))
        output.extend(b"\0" * (start - len(output)))
        raw = bytes(sections[name])
        offset = len(output)
        output.extend(raw)
        entries.append((name, offset, len(raw), len(raw), 0, hashlib.sha256(raw).digest()))
    toc_offset = _align(len(output))
    output.extend(b"\0" * (toc_offset - len(output)))
    for name, offset, stored_size, raw_size, codec, digest in entries:
        encoded_name = name.encode("utf-8")
        if len(encoded_name) > 65535:
            raise ValueError("V4 section name is too long")
        output.extend(
            _ENTRY_HEAD.pack(len(encoded_name), offset, stored_size, raw_size, codec, _ALIGNMENT)
        )
        output.extend(digest)
        output.extend(encoded_name)
    _HEADER.pack_into(output, 0, MAGIC, schema, len(entries), toc_offset)
    return bytes(output)


def loads(data: bytes | bytearray | memoryview) -> V4Container:
    view = memoryview(data)
    if len(view) < _HEADER.size:
        raise ValueError("truncated V4 container header")
    magic, schema, count, toc_offset = _HEADER.unpack_from(view, 0)
    if magic != MAGIC or schema != SCHEMA:
        raise ValueError("unsupported Lexcompact V4 container")
    if toc_offset < _HEADER.size or toc_offset > len(view):
        raise ValueError("invalid V4 table-of-contents offset")
    cursor = toc_offset
    sections: dict[str, memoryview] = {}
    previous_name = ""
    ranges: list[tuple[int, int]] = []
    for _ in range(count):
        if cursor + _ENTRY_HEAD.size + _HASH_SIZE > len(view):
            raise ValueError("truncated V4 table of contents")
        name_size, offset, stored_size, raw_size, codec, alignment = _ENTRY_HEAD.unpack_from(
            view, cursor
        )
        cursor += _ENTRY_HEAD.size
        digest = bytes(view[cursor : cursor + _HASH_SIZE])
        cursor += _HASH_SIZE
        if cursor + name_size > len(view):
            raise ValueError("truncated V4 section name")
        try:
            name = bytes(view[cursor : cursor + name_size]).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("invalid V4 section name") from exc
        cursor += name_size
        if not name or name <= previous_name or "/" in name or "\\" in name or name in {".", ".."}:
            raise ValueError("V4 section names must be sorted and safe")
        if codec != 0 or raw_size != stored_size or alignment != _ALIGNMENT:
            raise ValueError("unsupported V4 section encoding")
        end = offset + stored_size
        if offset < _HEADER.size or end > toc_offset or offset % alignment:
            raise ValueError("invalid V4 section offset")
        if any(offset < old_end and old_start < end for old_start, old_end in ranges):
            raise ValueError("overlapping V4 sections")
        section = view[offset:end]
        if hashlib.sha256(section).digest() != digest:
            raise ValueError(f"V4 section integrity check failed: {name}")
        sections[name] = section
        ranges.append((offset, end))
        previous_name = name
    return V4Container(sections, schema=schema, owner=data)


def load(path: str | Path) -> V4Container:
    with Path(path).open("rb") as handle:
        mapped = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
    try:
        return _with_owner(loads(memoryview(mapped)), mapped)
    except Exception:
        mapped.close()
        raise


def _with_owner(container: V4Container, owner: Any) -> V4Container:
    return V4Container(container._sections, schema=container.schema, owner=owner)


def load_traversable(resource: Any) -> V4Container:
    if isinstance(resource, (str, Path)):
        return load(resource)
    path = getattr(resource, "__fspath__", None)
    if path is not None:
        return load(path())
    return loads(resource.read_bytes())


__all__ = [
    "MAGIC",
    "SCHEMA",
    "Section",
    "V4Container",
    "dumps",
    "load",
    "load_traversable",
    "loads",
]
