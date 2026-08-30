"""Deterministic G2Lex v1 container builder and reader."""

from __future__ import annotations

import hashlib
import json
import struct
import zlib
from collections.abc import Mapping
from itertools import pairwise
from pathlib import Path

from .key_index import FrontCodedKeyIndex
from .model import SourceInfo, TypedLexiconData
from .record_store import MAX_RECORD_BLOCK_BYTES, compress_block, encode_record_block, encode_tags
from .value import LexiconValue, logical_sha256

MAGIC = b"G2LX"
SCHEMA = 1

_RESERVED_MANIFEST_KEYS = frozenset(
    {
        "format",
        "schema",
        "entry_count",
        "value_model",
        "key_index",
        "record_codec",
        "record_block_entries",
        "key_block_entries",
        "source",
        "logical_sha256",
        "build",
    }
)


def _validate_manifest_metadata(metadata: Mapping[str, object], label: str) -> None:
    conflicts = sorted(_RESERVED_MANIFEST_KEYS.intersection(metadata))
    if conflicts:
        names = ", ".join(repr(key) for key in conflicts)
        raise ValueError(f"{label} metadata contains reserved manifest keys: {names}")


HEADER = struct.Struct(">4sIIIIQQ")
TOC_PREFIX = struct.Struct(">I")
TOC_ENTRY = struct.Struct(">QQQIB3x32s")
DIR_HEADER = struct.Struct(">4sIII")
DIR_ENTRY = struct.Struct(">QQQII")


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _align(position: int, alignment: int = 8) -> int:
    return (position + alignment - 1) // alignment * alignment


def _source_dict(source: SourceInfo) -> dict[str, object]:
    value = source.canonical_dict()
    value["path"] = Path(source.path).name if source.path else None
    return value


def _record_directory(
    descriptors: list[tuple[int, int, int, int, int]], block_entries: int, count: int
) -> bytes:
    return DIR_HEADER.pack(b"RDIR", block_entries, count, len(descriptors)) + b"".join(
        DIR_ENTRY.pack(*descriptor) for descriptor in descriptors
    )


def _read_directory(
    data: memoryview,
) -> tuple[int, int, tuple[tuple[int, int, int, int, int], ...]]:
    if len(data) < DIR_HEADER.size:
        raise ValueError("truncated record directory")
    magic, block_entries, count, block_count = DIR_HEADER.unpack_from(data)
    if magic != b"RDIR" or block_entries == 0:
        raise ValueError("invalid record directory")
    expected = (count + block_entries - 1) // block_entries
    if block_count != expected or len(data) != DIR_HEADER.size + block_count * DIR_ENTRY.size:
        raise ValueError("record directory count mismatch")
    descriptors = tuple(
        DIR_ENTRY.unpack_from(data, DIR_HEADER.size + index * DIR_ENTRY.size)
        for index in range(block_count)
    )
    previous = 0
    for stored_offset, stored_size, raw_size, record_count, _ in descriptors:
        if (
            stored_offset < previous
            or stored_size == 0
            or raw_size == 0
            or stored_size > MAX_RECORD_BLOCK_BYTES
            or raw_size > MAX_RECORD_BLOCK_BYTES
        ):
            raise ValueError("invalid record directory descriptor")
        previous = stored_offset + stored_size
        if record_count == 0 or record_count > block_entries:
            raise ValueError("invalid record directory record count")
    if sum(item[3] for item in descriptors) != count:
        raise ValueError("record directory total mismatch")
    return block_entries, count, descriptors


def _build_container(sections: Mapping[str, bytes], *, flags: int = 0) -> bytes:
    if not sections:
        raise ValueError("G2Lex container needs sections")
    names = sorted(sections)
    output = bytearray(HEADER.size)
    descriptors: list[tuple[bytes, int, int, int, int, bytes]] = []
    for name in names:
        name_bytes = name.encode("utf-8")
        if not name_bytes or len(name_bytes) > 65535:
            raise ValueError("invalid section name")
        position = _align(len(output))
        output.extend(b"\0" * (position - len(output)))
        payload = bytes(sections[name])
        output.extend(payload)
        descriptors.append(
            (name_bytes, position, len(payload), len(payload), 8, hashlib.sha256(payload).digest())
        )
    toc_offset = _align(len(output))
    output.extend(b"\0" * (toc_offset - len(output)))
    toc = bytearray(TOC_PREFIX.pack(len(descriptors)))
    for name_bytes, offset, stored_size, raw_size, alignment, digest in descriptors:
        toc.extend(struct.pack(">H", len(name_bytes)))
        toc.extend(name_bytes)
        toc.extend(TOC_ENTRY.pack(offset, stored_size, raw_size, alignment, 0, digest))
    output.extend(toc)
    file_size = len(output)
    HEADER.pack_into(output, 0, MAGIC, SCHEMA, len(descriptors), flags, 0, toc_offset, file_size)
    return bytes(output)


def pack_typed(
    data: TypedLexiconData | Mapping[str, LexiconValue],
    *,
    source: SourceInfo | None = None,
    metadata: Mapping[str, object] | None = None,
    record_block_entries: int = 256,
    key_block_entries: int = 32,
    compression: str = "zlib",
    compression_level: int = 9,
) -> bytes:
    """Build a deterministic G2Lex file from typed logical entries."""

    if isinstance(data, TypedLexiconData):
        entries = data.entries
        source = source or data.source
        inherited = data.metadata
    else:
        entries = dict(data)
        inherited = {}
        source = source or SourceInfo()
    _validate_manifest_metadata(inherited, "inherited")
    if metadata is not None:
        _validate_manifest_metadata(metadata, "explicit")
    if record_block_entries <= 0 or key_block_entries <= 0:
        raise ValueError("block sizes must be positive")
    ordered_words = sorted(entries, key=lambda word: word.encode("utf-8"))
    tags = sorted(
        {tag for value in entries.values() if hasattr(value, "items") for tag, _ in value.items},
        key=lambda tag: tag.encode("utf-8"),
    )
    tag_ids = {tag: index for index, tag in enumerate(tags)}
    key_data = FrontCodedKeyIndex.encode(ordered_words, key_block_entries)
    stored_blocks = bytearray()
    descriptors = []
    for start in range(0, len(ordered_words), record_block_entries):
        values = [entries[word] for word in ordered_words[start : start + record_block_entries]]
        raw = encode_record_block(values, tag_ids)
        stored = compress_block(raw, compression, compression_level)
        offset = len(stored_blocks)
        stored_blocks.extend(stored)
        descriptors.append(
            (offset, len(stored), len(raw), len(values), zlib.crc32(raw) & 0xFFFFFFFF)
        )
    records_dir = _record_directory(descriptors, record_block_entries, len(ordered_words))
    manifest: dict[str, object] = {
        "format": "g2lex.lexicon.v1",
        "schema": SCHEMA,
        "entry_count": len(entries),
        "value_model": "typed-v1",
        "key_index": "front-coded-v1",
        "record_codec": f"{compression}-block-v1",
        "record_block_entries": record_block_entries,
        "key_block_entries": key_block_entries,
        "source": _source_dict(source),
        "logical_sha256": logical_sha256(entries),
        "build": {"deterministic": True},
    }
    manifest.update(inherited)
    if metadata:
        manifest.update(dict(metadata))
    sections = {
        "manifest.json": _json_bytes(manifest),
        "keys.fci": key_data,
        "records.blocks": bytes(stored_blocks),
        "records.dir": records_dir,
        "tags.bin": encode_tags(tags),
    }
    return _build_container(sections)


class BinaryLexiconContainer:
    """Validated read-only view of a G2Lex container."""

    def __init__(self, data: bytes | bytearray | memoryview):
        self._view = memoryview(data)
        if len(self._view) < HEADER.size:
            raise ValueError("truncated G2Lex header")
        magic, schema, count, _flags, _reserved, toc_offset, file_size = HEADER.unpack_from(
            self._view
        )
        if magic != MAGIC:
            raise ValueError("invalid G2Lex magic")
        if schema != SCHEMA:
            raise ValueError(f"unsupported G2Lex schema: {schema}")
        if (
            file_size != len(self._view)
            or toc_offset < HEADER.size
            or toc_offset + 4 > len(self._view)
        ):
            raise ValueError("invalid G2Lex file size or TOC offset")
        toc_count = TOC_PREFIX.unpack_from(self._view, toc_offset)[0]
        if toc_count != count:
            raise ValueError("G2Lex section count mismatch")
        position = toc_offset + TOC_PREFIX.size
        sections: dict[str, tuple[int, int, int, int, bytes]] = {}
        for _ in range(count):
            if position + 2 > len(self._view):
                raise ValueError("truncated G2Lex v1 TOC")
            name_length = struct.unpack_from(">H", self._view, position)[0]
            position += 2
            end_name = position + name_length
            if end_name + TOC_ENTRY.size > len(self._view):
                raise ValueError("truncated G2Lex v1 TOC entry")
            try:
                name = bytes(self._view[position:end_name]).decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("invalid G2Lex section name") from exc
            position = end_name
            offset, stored_size, raw_size, alignment, codec, digest = TOC_ENTRY.unpack_from(
                self._view, position
            )
            position += TOC_ENTRY.size
            if not name or name in sections or codec != 0 or alignment == 0:
                raise ValueError("invalid G2Lex section descriptor")
            if offset < HEADER.size or offset + stored_size > toc_offset or offset % alignment:
                raise ValueError("G2Lex section lies outside payload or is misaligned")
            payload = self._view[offset : offset + stored_size]
            if raw_size != stored_size or hashlib.sha256(payload).digest() != digest:
                raise ValueError(f"G2Lex section hash/size mismatch: {name}")
            sections[name] = (offset, stored_size, raw_size, alignment, digest)
        ranges = sorted((value[0], value[0] + value[1]) for value in sections.values())
        if any(left < right for (_, right), (left, _) in pairwise(ranges)):
            raise ValueError("overlapping G2Lex sections")
        if position > len(self._view):
            raise ValueError("truncated G2Lex v1 TOC")
        self._sections = sections
        self.manifest = self._read_manifest()
        if self.manifest.get("format") != "g2lex.lexicon.v1":
            raise ValueError("invalid G2Lex manifest format")
        if int(str(self.manifest.get("schema", -1))) != SCHEMA:
            raise ValueError("G2Lex manifest schema mismatch")
        required = {"manifest.json", "keys.fci", "records.blocks", "records.dir", "tags.bin"}
        if not required.issubset(self._sections):
            raise ValueError("G2Lex container is missing required sections")
        self.key_index = FrontCodedKeyIndex(self.section_view("keys.fci"))
        from .record_store import decode_tags

        self.tags = decode_tags(self.section_view("tags.bin"))
        block_entries, count, descriptors = _read_directory(self.section_view("records.dir"))
        if count != len(self.key_index) or count != int(str(self.manifest.get("entry_count", -1))):
            raise ValueError("G2Lex logical count mismatch")
        codec = str(self.manifest.get("record_codec", ""))
        if codec not in {"none-block-v1", "zlib-block-v1"}:
            raise ValueError("unsupported G2Lex v1 record codec")
        records_size = len(self.section_view("records.blocks"))
        for offset, stored_size, _raw_size, _record_count, _crc in descriptors:
            if offset + stored_size > records_size:
                raise ValueError("record directory points outside records section")
        self.record_block_entries = block_entries
        self.record_count = count
        self.record_descriptors = descriptors

    def _read_manifest(self) -> dict[str, object]:
        if "manifest.json" not in self._sections:
            raise ValueError("G2Lex container is missing manifest.json")
        try:
            value = json.loads(bytes(self.section_view("manifest.json")))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid G2Lex manifest") from exc
        if not isinstance(value, dict):
            raise TypeError("G2Lex manifest must be an object")
        return value

    def section_view(self, name: str) -> memoryview:
        try:
            offset, size, _raw_size, _alignment, _digest = self._sections[name]
        except KeyError as exc:
            raise KeyError(name) from exc
        return self._view[offset : offset + size]

    def section_bytes(self, name: str) -> bytes:
        return bytes(self.section_view(name))

    def __contains__(self, name: object) -> bool:
        return name in self._sections

    def __iter__(self):
        return iter(self._sections)

    def __len__(self) -> int:
        return len(self._sections)

    @classmethod
    def from_bytes(cls, data: bytes) -> BinaryLexiconContainer:
        return cls(data)
