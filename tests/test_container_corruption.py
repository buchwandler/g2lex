from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import pytest

from g2lex import WORD_ONLY, TaggedValue, TypedLexiconData, open_bytes
from g2lex.container import dumps as dumps_v4
from g2lex.container import load as load_v4
from g2lex.container import load_traversable
from g2lex.container import loads as loads_v4
from g2lex.format import (
    HEADER,
    TOC_ENTRY,
    TOC_PREFIX,
    BinaryLexiconContainer,
    _build_container,
    pack_typed,
)


def _v1_layout(raw: bytes) -> tuple[int, list[tuple[int, int, int, int, int]]]:
    _magic, _schema, count, _flags, _reserved, toc, _size = HEADER.unpack_from(raw)
    cursor = toc + TOC_PREFIX.size
    entries = []
    for _ in range(count):
        name_size = struct.unpack_from(">H", raw, cursor)[0]
        cursor += 2 + name_size
        entries.append((cursor, *TOC_ENTRY.unpack_from(raw, cursor)))
        cursor += TOC_ENTRY.size
    return toc, entries


def _v1_descriptor(raw: bytes, name: str) -> tuple[int, int, int, int, int, bytes]:
    toc, _ = _v1_layout(raw)
    count = struct.unpack_from(">I", raw, toc)[0]
    cursor = toc + 4
    for _ in range(count):
        name_size = struct.unpack_from(">H", raw, cursor)[0]
        cursor += 2
        section_name = bytes(raw[cursor : cursor + name_size]).decode()
        cursor += name_size
        descriptor = TOC_ENTRY.unpack_from(raw, cursor)
        if section_name == name:
            return descriptor
        cursor += TOC_ENTRY.size
    raise AssertionError(name)


def _rewrite_v1_digest(raw: bytearray, name: str) -> None:
    toc, _ = _v1_layout(raw)
    count = struct.unpack_from(">I", raw, toc)[0]
    cursor = toc + 4
    for _ in range(count):
        name_size = struct.unpack_from(">H", raw, cursor)[0]
        cursor += 2
        section_name = bytes(raw[cursor : cursor + name_size]).decode()
        cursor += name_size
        descriptor_at = cursor
        offset, stored, _raw_size, _alignment, _codec, _digest = TOC_ENTRY.unpack_from(raw, cursor)
        if section_name == name:
            digest_at = descriptor_at + 32
            raw[digest_at : digest_at + 32] = hashlib.sha256(raw[offset : offset + stored]).digest()
            return
        cursor += TOC_ENTRY.size
    raise AssertionError(name)


def _valid_v1() -> bytes:
    return pack_typed(
        TypedLexiconData(
            {"alpha": "a", "beta": WORD_ONLY, "tag": TaggedValue((("DEFAULT", "t"),))}
        ),
        record_block_entries=2,
        key_block_entries=2,
        compression="none",
    )


@pytest.mark.parametrize(
    "field, value, message",
    [
        ("magic", b"bad!", "magic"),
        ("schema", 99, "schema"),
        ("file_size", 1, "file size"),
        ("toc", 1, "file size"),
        ("count", 99, "section count"),
    ],
)
def test_v1_header_corruption(field: str, value: object, message: str) -> None:
    raw = bytearray(_valid_v1())
    positions = {"magic": 0, "schema": 4, "count": 8, "toc": 20, "file_size": 28}
    if field == "magic":
        raw[:4] = value  # type: ignore[index]
    else:
        struct.pack_into(">I" if field != "file_size" else ">Q", raw, positions[field], value)
    with pytest.raises(ValueError, match=message):
        BinaryLexiconContainer(raw)


def test_v1_toc_and_section_descriptor_corruption() -> None:
    raw = bytearray(_valid_v1())
    toc, _ = _v1_layout(raw)

    for mutation, message in (
        (lambda b: struct.pack_into(">I", b, 20, len(b) + 1), "file size"),
        (lambda b: struct.pack_into(">I", b, toc, 0), "section count"),
        (lambda b: struct.pack_into(">H", b, toc + 4, 0), "descriptor"),
    ):
        candidate = bytearray(_valid_v1())
        mutation(candidate)
        with pytest.raises(ValueError, match=message):
            BinaryLexiconContainer(candidate)

    # Point a section beyond the TOC, and independently corrupt alignment/codec.
    for offset, alignment, codec, message in (
        (len(raw) + 100, 8, 0, "outside payload"),
        (_v1_descriptor(raw, "keys.fci")[0], 0, 0, "descriptor"),
        (_v1_descriptor(raw, "keys.fci")[0], 8, 1, "descriptor"),
    ):
        candidate = bytearray(_valid_v1())
        descriptor_at = _v1_layout(candidate)[1][0][0]
        struct.pack_into(">Q", candidate, descriptor_at, offset)
        struct.pack_into(">I", candidate, descriptor_at + 24, alignment)
        candidate[descriptor_at + 28] = codec
        with pytest.raises(ValueError):
            BinaryLexiconContainer(candidate)

    # A payload mutation is reported as a hash/size failure.
    candidate = bytearray(_valid_v1())
    offset, _stored, *_ = _v1_descriptor(candidate, "keys.fci")
    candidate[offset] ^= 1
    with pytest.raises(ValueError, match="hash/size"):
        BinaryLexiconContainer(candidate)


def test_v1_manifest_and_required_section_validation() -> None:
    raw = bytearray(_valid_v1())
    offset, stored, *_ = _v1_descriptor(raw, "manifest.json")
    raw[offset : offset + stored] = b"not json" + b" " * (stored - len(b"not json"))
    _rewrite_v1_digest(raw, "manifest.json")
    with pytest.raises(ValueError, match="manifest"):
        BinaryLexiconContainer(raw)

    raw = bytearray(_valid_v1())
    offset, stored, *_ = _v1_descriptor(raw, "manifest.json")
    raw[offset : offset + stored] = b"[]\n" + b" " * (stored - 3)
    _rewrite_v1_digest(raw, "manifest.json")
    with pytest.raises(TypeError, match="object"):
        BinaryLexiconContainer(raw)

    for key, replacement, expected in (
        ("format", "x", "manifest format"),
        ("schema", 2, "schema mismatch"),
    ):
        raw = bytearray(_valid_v1())
        offset, stored, *_ = _v1_descriptor(raw, "manifest.json")
        manifest = json.loads(bytes(raw[offset : offset + stored]))
        manifest[key] = replacement
        encoded = (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
        assert len(encoded) <= stored
        raw[offset : offset + stored] = encoded.ljust(stored, b" ")
        _rewrite_v1_digest(raw, "manifest.json")
        with pytest.raises(ValueError, match=expected):
            BinaryLexiconContainer(raw)

    # Required sections are checked after successful container parsing.
    sections = {
        name: b"x"
        for name in ("manifest.json", "keys.fci", "records.blocks", "records.dir", "tags.bin")
    }
    for missing in sections:
        candidate = dict(sections)
        candidate.pop(missing)
        with pytest.raises((ValueError, TypeError)):
            BinaryLexiconContainer(_build_container(candidate))


def test_v1_record_directory_and_pack_validation() -> None:
    with pytest.raises(ValueError, match="positive"):
        pack_typed({"a": "x"}, record_block_entries=0)
    with pytest.raises(ValueError, match="positive"):
        pack_typed({"a": "x"}, key_block_entries=-1)
    assert open_bytes(pack_typed({"a": "x"}, compression="none"))["a"] == "x"
    assert open_bytes(pack_typed({"a": "x"}, compression="zlib"))["a"] == "x"
    with pytest.raises(ValueError, match="sections"):
        _build_container({})
    with pytest.raises(ValueError, match="section name"):
        _build_container({"": b"x"})
    with pytest.raises(ValueError, match="section name"):
        _build_container({"é" * 40000: b"x"})

    raw = bytearray(_valid_v1())
    offset, _stored, *_ = _v1_descriptor(raw, "records.dir")
    # RDIR header's block count is the final uint32.
    struct.pack_into(">I", raw, offset + 12, 99)
    _rewrite_v1_digest(raw, "records.dir")
    with pytest.raises(ValueError, match="record directory"):
        BinaryLexiconContainer(raw)


def _valid_v4() -> bytes:
    return dumps_v4({"alpha": b"one", "beta": b"two"})


def _v4_entry(raw: bytes, index: int = 0) -> tuple[int, int, int, int, int, int, int]:
    _magic, _schema, count, toc = struct.unpack_from("<4sIIQ", raw)
    cursor = toc
    for current in range(count):
        start = cursor
        head = struct.unpack_from("<HQQQBI", raw, cursor)
        name_size = head[0]
        cursor += struct.calcsize("<HQQQBI") + 32 + name_size
        if current == index:
            return (start, *head)
    raise AssertionError(index)


def test_v4_corruption_matrix_and_traversable_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = _valid_v4()
    for mutate, message in (
        (lambda b: b.__setitem__(slice(0, 4), b"bad!"), "unsupported"),
        (lambda b: struct.pack_into("<I", b, 4, 3), "unsupported"),
        (lambda b: struct.pack_into("<Q", b, 12, len(b) + 1), "offset"),
    ):
        candidate = bytearray(raw)
        mutate(candidate)
        with pytest.raises(ValueError, match=message):
            loads_v4(candidate)

    start, _, _, stored, _, _, _ = _v4_entry(raw)
    for field, value, message in (
        ("name_size", 65535, "name"),
        ("offset", 1, "offset"),
        ("stored", stored + 1, "encoding"),
        ("raw", stored + 1, "encoding"),
        ("codec", 1, "encoding"),
        ("alignment", 4, "encoding"),
    ):
        candidate = bytearray(raw)
        position = {
            "name_size": start,
            "offset": start + 2,
            "stored": start + 10,
            "raw": start + 18,
            "codec": start + 26,
            "alignment": start + 27,
        }[field]
        fmt = (
            "<H"
            if field == "name_size"
            else (
                "<B"
                if field in {"codec"}
                else "<Q"
                if field in {"offset", "stored", "raw"}
                else "<I"
            )
        )
        struct.pack_into(fmt, candidate, position, value)
        with pytest.raises(ValueError, match=message):
            loads_v4(candidate)

    candidate = bytearray(raw)
    digest_at = start + struct.calcsize("<HQQQBI")
    candidate[digest_at] ^= 1
    with pytest.raises(ValueError, match="integrity"):
        loads_v4(candidate)

    path = tmp_path / "x.lxc"
    path.write_bytes(raw)
    assert bytes(load_v4(path)["alpha"]) == b"one"
    assert bytes(load_traversable(path)["beta"]) == b"two"

    class Fspath:
        def __fspath__(self) -> str:
            return str(path)

    class BytesResource:
        def read_bytes(self) -> bytes:
            return raw

    assert bytes(load_traversable(Fspath())["alpha"]) == b"one"
    assert bytes(load_traversable(BytesResource())["alpha"]) == b"one"

    def fail(_data: object) -> None:
        raise ValueError("parse failure")

    monkeypatch.setattr("g2lex.container.loads", fail)
    with pytest.raises(ValueError, match="parse failure"):
        load_v4(path)
