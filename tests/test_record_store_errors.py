from __future__ import annotations

import struct
import zlib

import pytest

from g2lex import WORD_ONLY, TaggedValue
from g2lex.record_store import (
    MAX_RECORD_BLOCK_BYTES,
    STRING_LIST_TYPE,
    TAG_MAP_TYPE,
    compress_block,
    decode_record,
    decode_record_block,
    decode_tags,
    decode_varint,
    decompress_block,
    encode_record,
    encode_record_block,
    encode_tags,
    encode_varint,
)


def test_varint_boundaries_and_failures() -> None:
    values = [0, 127, 128, 16384, (1 << 64) - 1]
    for value in values:
        encoded = encode_varint(value)
        assert decode_varint(memoryview(encoded), 0, len(encoded)) == (value, len(encoded))

    with pytest.raises(ValueError, match="negative"):
        encode_varint(-1)
    with pytest.raises(ValueError, match="varint"):
        decode_varint(memoryview(b"\x80"), 0, 1)
    with pytest.raises(ValueError, match="varint"):
        decode_varint(memoryview(b"\x80" * 10), 0, 10)
    with pytest.raises(ValueError, match="varint"):
        decode_varint(memoryview(b"\xff" * 9 + b"\x02"), 0, 10)


def test_text_and_selector_decoding_errors() -> None:
    assert decode_record(encode_record("hé", {}), ()) == "hé"
    with pytest.raises(ValueError, match="truncated record string"):
        decode_record(b"\x02\x05ab", ())
    with pytest.raises(ValueError, match="invalid UTF-8"):
        decode_record(b"\x02\x01\xff", ())

    tags = ("DEFAULT", "ALT")
    selectors = (None, "ipa", ("first", "second"), ())
    for selector in selectors:
        value = TaggedValue((("DEFAULT", selector),))
        assert decode_record(encode_record(value, {"DEFAULT": 0}), tags) == value

    with pytest.raises(ValueError, match="truncated selector"):
        decode_record(bytes((TAG_MAP_TYPE, 1, 0)), tags)
    with pytest.raises(ValueError, match="invalid selector type"):
        decode_record(bytes((TAG_MAP_TYPE, 1, 0, 99)), tags)
    with pytest.raises(ValueError, match="truncated record string"):
        decode_record(bytes((TAG_MAP_TYPE, 1, 0, STRING_LIST_TYPE, 1, 3, ord("x"))), tags)


def test_record_value_variants_and_validation() -> None:
    values = [
        WORD_ONLY,
        "pronunciation",
        ("one", "two"),
        TaggedValue((("DEFAULT", None),)),
        TaggedValue((("DEFAULT", "d"),)),
        TaggedValue((("DEFAULT", ("a", "b")),)),
    ]
    tag_ids = {"DEFAULT": 0}
    for value in values:
        assert decode_record(encode_record(value, tag_ids), ("DEFAULT",)) == value

    with pytest.raises(ValueError, match="missing"):
        encode_record(TaggedValue((("MISSING", "x"),)), tag_ids)
    with pytest.raises(TypeError, match="unsupported"):
        encode_record(42, tag_ids)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="empty"):
        decode_record(b"", ())
    with pytest.raises(ValueError, match="invalid record type"):
        decode_record(b"\xff", ())
    with pytest.raises(ValueError, match="trailing"):
        decode_record(b"\x00\x00", ())
    with pytest.raises(ValueError, match="unknown tag"):
        decode_record(bytes((TAG_MAP_TYPE, 1, 4, 1)), ("DEFAULT",))


def test_record_blocks_valid_and_corrupt() -> None:
    values = [WORD_ONLY, "x", ("a", "b"), TaggedValue((("DEFAULT", "p"),))]
    block = encode_record_block(values, {"DEFAULT": 0})
    assert decode_record_block(block, ("DEFAULT",)) == tuple(values)
    assert decode_record_block(encode_record_block([], {}), ()) == ()
    assert decode_record_block(encode_record_block(["x"], {}), ()) == ("x",)

    with pytest.raises(ValueError, match="truncated record block"):
        decode_record_block(b"\x00\x00", ())
    short_table = struct.pack(">I", 1) + struct.pack(">I", 0)
    with pytest.raises(ValueError, match="offsets"):
        decode_record_block(short_table, ())

    def with_offsets(offsets: list[int], payload: bytes = b"\x00") -> bytes:
        return (
            struct.pack(">I", len(offsets) - 1)
            + b"".join(struct.pack(">I", item) for item in offsets)
            + payload
        )

    with pytest.raises(ValueError, match="offsets"):
        decode_record_block(with_offsets([1, 1]), ())
    with pytest.raises(ValueError, match="offsets"):
        decode_record_block(with_offsets([1, 0]), ())
    with pytest.raises(ValueError, match="size"):
        decode_record_block(with_offsets([0, 2]), ())
    corrupt = bytearray(encode_record_block(["x"], {}))
    corrupt[-1] = 0xFF
    with pytest.raises(ValueError, match="UTF-8"):
        decode_record_block(corrupt, ())


def test_compression_codecs_and_failures() -> None:
    raw = b"record payload" * 4
    assert compress_block(raw, "none") == raw
    assert decompress_block(raw, "none", len(raw)) == raw
    compressed = compress_block(raw, "zlib")
    assert decompress_block(compressed, "zlib", len(raw)) == raw

    with pytest.raises(ValueError, match="unsupported"):
        compress_block(raw, "brotli")
    with pytest.raises(ValueError, match="unsupported"):
        decompress_block(raw, "brotli", len(raw))
    with pytest.raises(ValueError, match="safety"):
        decompress_block(b"", "none", -1)
    with pytest.raises(ValueError, match="safety"):
        decompress_block(b"", "none", MAX_RECORD_BLOCK_BYTES + 1)
    with pytest.raises(ValueError, match="compressed"):
        decompress_block(b"not-zlib", "zlib", 1)
    with pytest.raises(ValueError, match="compressed"):
        decompress_block(zlib.compress(raw) + b"tail", "zlib", len(raw))
    with pytest.raises(ValueError, match="raw size"):
        decompress_block(compressed, "zlib", len(raw) + 1)
    with pytest.raises(ValueError, match="raw size"):
        decompress_block(compressed, "zlib", len(raw) - 1)


def test_tag_tables_and_corruptions() -> None:
    assert decode_tags(encode_tags([])) == ()
    assert decode_tags(encode_tags(["DEFAULT", "étiquette"])) == ("DEFAULT", "étiquette")
    for payload, message in (
        (b"bad!" + b"\x00" * 4, "invalid"),
        (b"TAG1\x00\x00\x00", "invalid"),
        (b"TAG1\x00\x00\x00\x01\x01", "truncated"),
        (b"TAG1\x00\x00\x00\x01\x01\xff", "UTF-8"),
        (encode_tags(["x", "x"]), "contents"),
        (encode_tags(["x"]) + b"tail", "contents"),
    ):
        with pytest.raises(ValueError, match=message):
            decode_tags(payload)
