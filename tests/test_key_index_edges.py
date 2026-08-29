from __future__ import annotations

import struct

import pytest

from g2lex.key_index import FrontCodedKeyIndex


def _parts(raw: bytes) -> tuple[int, int, int]:
    _magic, block_entries, key_count, block_count = struct.unpack_from(">4sIII", raw)
    return block_entries, key_count, block_count


def _body_start(raw: bytes) -> int:
    return 16 + 4 * (_parts(raw)[2] + 1)


def test_unicode_roundtrip_find_and_ordinals() -> None:
    keys = ["a", "aardvark", "alpha", "alphabet", "é", "éclair", "你好", "𐐀"]
    ordered = sorted(keys, key=lambda item: item.encode())
    index = FrontCodedKeyIndex(FrontCodedKeyIndex.encode(keys, block_entries=2))
    assert list(index) == ordered
    assert tuple(index.first_keys()) == tuple(ordered[::2])
    for ordinal, key in enumerate(ordered):
        assert index.key_at(ordinal) == key
        assert index.find(key) == ordinal
    assert index.find("") is None
    assert index.find("0") is None
    assert index.find("éz") is None
    assert index.find(42) is None  # type: ignore[arg-type]
    assert len(FrontCodedKeyIndex.encode([], 2)) == 20
    empty = FrontCodedKeyIndex(FrontCodedKeyIndex.encode([], 2))
    assert len(empty) == 0 and empty.find("x") is None and tuple(empty) == ()


def test_encoder_rejects_duplicates_and_invalid_block_size() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        FrontCodedKeyIndex.encode(["x", "x"])
    with pytest.raises(ValueError, match="positive"):
        FrontCodedKeyIndex.encode(["x"], 0)
    with pytest.raises(ValueError, match="positive"):
        FrontCodedKeyIndex.encode(["x"], -1)


def test_header_and_offset_corruption() -> None:
    valid = FrontCodedKeyIndex.encode(["a", "b", "c"], 2)
    for mutate, message in (
        (lambda b: b.__setitem__(slice(0, 4), b"bad!"), "header"),
        (lambda b: struct.pack_into(">I", b, 4, 0), "header"),
        (lambda b: struct.pack_into(">I", b, 12, 9), "header"),
    ):
        candidate = bytearray(valid)
        mutate(candidate)
        with pytest.raises(ValueError, match=message):
            FrontCodedKeyIndex(candidate)

    with pytest.raises(ValueError, match="offsets"):
        FrontCodedKeyIndex(valid[:19])
    candidate = bytearray(valid)
    body = _body_start(valid)
    struct.pack_into(">I", candidate, 16, 1000)
    with pytest.raises(ValueError, match="offset"):
        FrontCodedKeyIndex(candidate)
    candidate = bytearray(valid)
    struct.pack_into(">I", candidate, 24, 5)
    with pytest.raises(ValueError, match="offset"):
        FrontCodedKeyIndex(candidate)
    assert body < len(valid)


def test_block_corruption_and_varint_bounds() -> None:
    valid = FrontCodedKeyIndex.encode(["alpha", "alpine", "beta"], 2)
    body = _body_start(valid)

    # First record's prefix cannot exceed the empty previous key.
    candidate = bytearray(valid)
    candidate[body] = 1
    with pytest.raises(ValueError, match="truncated front-coded key"):
        list(FrontCodedKeyIndex(candidate))

    # A suffix length extending beyond the block is rejected.
    candidate = bytearray(valid)
    candidate[body + 1] = 0x7F
    with pytest.raises(ValueError, match="truncated front-coded key"):
        list(FrontCodedKeyIndex(candidate))

    # Invalid UTF-8 in a one-key block.
    one = bytearray(FrontCodedKeyIndex.encode(["x"], 1))
    one[_body_start(one) + 2] = 0xFF
    with pytest.raises(ValueError, match="UTF-8"):
        list(FrontCodedKeyIndex(one))

    # Add an otherwise unconsumed byte to the first block and update its end.
    candidate = bytearray(valid)
    first_end_at = 20
    first_end = struct.unpack_from(">I", candidate, first_end_at)[0]
    candidate.insert(body + first_end, 0)
    struct.pack_into(">I", candidate, first_end_at, first_end + 1)
    # The second offset moved by one as well.
    struct.pack_into(">I", candidate, 24, struct.unpack_from(">I", candidate, 24)[0] + 1)
    with pytest.raises(ValueError, match="trailing"):
        list(FrontCodedKeyIndex(candidate))

    with pytest.raises(ValueError, match="varint"):
        malformed = b"FCI1" + struct.pack(">III", 1, 1, 1) + struct.pack(">II", 0, 10)
        list(FrontCodedKeyIndex(malformed + b"\xff" * 9 + b"\x02"))


def test_find_boundaries_and_key_at_errors() -> None:
    keys = ["aa", "ab", "ac", "ba", "bb", "bc"]
    index = FrontCodedKeyIndex(FrontCodedKeyIndex.encode(keys, 2))
    assert index.find("aa") == 0
    assert index.find("ab") == 1
    assert index.find("bc") == 5
    assert index.find("a") is None
    assert index.find("az") is None
    assert index.find("zz") is None
    for ordinal in (-1, len(keys)):
        with pytest.raises(IndexError):
            index.key_at(ordinal)

    # Make a valid block structurally inconsistent with its declared entry count.
    candidate = bytearray(FrontCodedKeyIndex.encode(["a", "b"], 2))
    struct.pack_into(">I", candidate, 8, 3)
    with pytest.raises(ValueError, match="header"):
        FrontCodedKeyIndex(candidate)
