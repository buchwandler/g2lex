from __future__ import annotations

import struct

import pytest

from g2lex.literals import (
    BinaryPoolLiteralStore,
    RePairCodec,
    StringInterner,
    SymbolCodec,
    TokenSpacedCodec,
    VariantTupleInterner,
    _decode_variants,
)


def test_variant_decoder_and_binary_pool_roundtrip() -> None:
    assert _decode_variants(struct.pack("<I", 0)) == ()
    with pytest.raises(ValueError, match="truncated pronunciation record"):
        _decode_variants(b"\x00")
    with pytest.raises(ValueError, match="truncated pronunciation length"):
        _decode_variants(struct.pack("<I", 1) + b"x")
    with pytest.raises(ValueError, match="truncated pronunciation payload"):
        _decode_variants(struct.pack("<II", 1, 2) + b"x")
    with pytest.raises(ValueError, match="not UTF-8"):
        _decode_variants(struct.pack("<II", 1, 1) + b"\xff")
    with pytest.raises(ValueError, match="trailing"):
        _decode_variants(struct.pack("<I", 0) + b"tail")

    store = BinaryPoolLiteralStore({"a": ("x", "q"), "你好": ("ㄋㄧ3",)})
    assert store["a"] == ("x", "q")
    assert store.words == ("a", "你好")
    assert store.prefixes("你好x") == ("你好",)
    assert store.prefixes("") == ()
    assert store.mapped_bytes > 0
    assert store.resident_object_count_estimate == len(store.words) + 2 * (len(store.words) + 1)
    assert store.serialized_bytes == len(store.serialize())
    assert store.serialize_sections().keys() == {"literals.binary-pool"}
    restored = BinaryPoolLiteralStore.deserialize(store.serialize())
    assert {key: restored[key] for key in restored} == {"a": ("x", "q"), "你好": ("ㄋㄧ3",)}
    assert "missing" not in restored
    assert restored.get("missing", ()) == ()
    with pytest.raises(KeyError):
        restored["missing"]


def test_binary_pool_constructor_and_serialization_corruption() -> None:
    with pytest.raises(TypeError, match="pool arrays"):
        BinaryPoolLiteralStore()
    with pytest.raises(ValueError, match="offset arrays"):
        BinaryPoolLiteralStore(
            keys=("a",),
            key_offsets=(0,),
            key_pool=b"a",
            value_offsets=(0, 1),
            value_pool=b"\x00\x00\x00\x00",
        )

    store = BinaryPoolLiteralStore({"a": ("x",), "b": ("y",)})
    raw = store.serialize()
    count = 2
    table_end = 16 + 8 * (count + 1)
    key_size = len(store._key_pool)
    key_pool_at = table_end
    value_pool_at = table_end + key_size
    for payload, message in (
        (b"bad!" + raw[4:], "header"),
        (struct.pack("<4sIII", b"LIT2", 99, count, key_size) + raw[16:], "version"),
        (raw[:16], "offsets"),
    ):
        with pytest.raises(ValueError, match=message):
            BinaryPoolLiteralStore.deserialize(payload)

    bad = bytearray(raw)
    struct.pack_into("<I", bad, 16 + 4 * (count + 1) - 4, key_size + 1)
    with pytest.raises(ValueError, match="ranges"):
        BinaryPoolLiteralStore.deserialize(bad)
    bad = bytearray(raw)
    struct.pack_into("<I", bad, 16 + 8 * (count + 1) - 4, 0)
    with pytest.raises(ValueError, match="ranges"):
        BinaryPoolLiteralStore.deserialize(bad)

    bad = bytearray(raw)
    bad[key_pool_at] = 0xFF
    with pytest.raises(ValueError, match="UTF-8"):
        BinaryPoolLiteralStore.deserialize(bad)

    # Same-sized keys can be made unsorted or duplicate without changing tables.
    bad = bytearray(BinaryPoolLiteralStore({"a": ("x",), "b": ("y",)}).serialize())
    bad[key_pool_at] = ord("c")
    with pytest.raises(ValueError, match="sorted"):
        BinaryPoolLiteralStore.deserialize(bad)
    bad = bytearray(raw)
    bad[key_pool_at + 1] = ord("a")
    with pytest.raises(ValueError, match="sorted"):
        BinaryPoolLiteralStore.deserialize(bad)
    assert value_pool_at > key_pool_at


def test_interners_and_repair_codec_corruption() -> None:
    interner = StringInterner.from_values(["b", "a", "a"])
    assert interner.unique_count == 2
    assert interner.decode(interner.encode("a")) == "a"
    with pytest.raises(KeyError):
        interner.encode("missing")
    variants = VariantTupleInterner.from_values([("b",), ("a",), ("a",)])
    assert variants.decode(variants.encode(("a",))) == ("a",)

    codec = RePairCodec()
    assert codec.decode(codec.encode(b"")) == b""
    repetitive = b"abcabcabcabc"
    encoded = codec.encode(repetitive)
    assert codec.decode(encoded) == repetitive
    accounting = codec.accounting(repetitive)
    assert accounting["input_bytes"] == len(repetitive)
    assert accounting["encoded_bytes"] == len(encoded)
    for payload, message in (
        (b"bad!", "invalid"),
        (b"RPR1\x01\x00\x00\x00\x01", "dictionary"),
        (b"RPR1\x00\x00\x00\x00\x01", "payload"),
        (b"RPR1" + struct.pack("<II", 0, 0) + b"x", "size"),
    ):
        with pytest.raises(ValueError, match=message):
            codec.decode(payload)

    # A valid dictionary whose sequence contains an unknown high symbol.
    invalid_symbol = b"RPR1" + struct.pack("<I", 0) + struct.pack("<I", 1) + struct.pack("<H", 256)
    with pytest.raises(ValueError, match="symbol"):
        codec.decode(invalid_symbol)

    # A dictionary reference is expanded in reverse order; corrupt its shape.
    bad_dictionary = bytearray(codec.encode(b"abababab"))
    struct.pack_into("<H", bad_dictionary, 8, 999)
    with pytest.raises(ValueError, match="symbol|payload"):
        codec.decode(bad_dictionary)


def test_symbol_and_token_codecs() -> None:
    symbols = SymbolCodec("abˈ")
    assert symbols.codec_id == "symbol-u8"
    assert symbols.decode(symbols.encode("aˈb")) == "aˈb"
    with pytest.raises(ValueError, match="absent"):
        symbols.encode("z")

    wide = SymbolCodec(str(i) for i in range(256))
    assert wide.width == 2 and wide.codec_id == "symbol-u16"
    assert wide.decode(wide.encode("2550")) == "2550"
    with pytest.raises(ValueError, match="absent"):
        wide.encode("not-inventory")
    with pytest.raises(ValueError, match="inventory"):
        SymbolCodec(str(i) for i in range(65536))
    with pytest.raises(ValueError, match="truncated"):
        wide.decode(b"\x00")

    tokens = TokenSpacedCodec(["AH", "B", "CH"])
    assert tokens.codec_id == "token-spaced"
    encoded = tokens.encode_tokens(["AH", "CH"])
    assert tokens.decode_tokens(encoded) == ("AH", "CH")
    with pytest.raises(ValueError, match="absent"):
        tokens.encode_tokens(["missing"])
    wide_tokens = TokenSpacedCodec(str(i) for i in range(256))
    with pytest.raises(ValueError, match="truncated"):
        wide_tokens.decode_tokens(b"\x00")
