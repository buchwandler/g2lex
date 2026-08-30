from __future__ import annotations

import pytest

from g2lex.literals import BinaryPoolLiteralStore, InternedBinaryPoolLiteralStore


def test_interned_store_roundtrips_ordered_duplicate_variants() -> None:
    values = {
        "first": ("ʃ", "a", "ʃ"),
        "second": ("ʃ", "a", "ʃ"),
        "third": ("ʃ",),
    }
    store = InternedBinaryPoolLiteralStore(values)
    assert store.words == ("first", "second", "third")
    assert store["first"] == values["first"]
    assert store["second"] == values["second"]
    assert store["third"] == values["third"]
    restored = InternedBinaryPoolLiteralStore.deserialize(store.serialize())
    assert tuple(restored) == store.words
    assert restored["first"] == values["first"]
    assert restored.serialize() == store.serialize()
    assert store.serialize_sections().keys() == {"literals.interned-binary-pool"}


def test_interning_reuses_global_string_and_tuple_storage() -> None:
    values = {str(index): ("shared", "value") for index in range(20)}
    interned = InternedBinaryPoolLiteralStore(values)
    binary = BinaryPoolLiteralStore(values)
    assert len(interned._string_offsets) == 3
    assert interned.mapped_bytes < binary.mapped_bytes
    assert interned.resident_object_count_estimate == 2 * len(values)


def test_interned_store_rejects_corruption() -> None:
    store = InternedBinaryPoolLiteralStore({"word": ("value",)})
    with pytest.raises(ValueError):
        InternedBinaryPoolLiteralStore.deserialize(store.serialize()[:-1])
    bad = bytearray(store.serialize())
    bad[4:8] = (2).to_bytes(4, "little")
    with pytest.raises(ValueError, match="version"):
        InternedBinaryPoolLiteralStore.deserialize(bad)
