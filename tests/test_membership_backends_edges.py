from __future__ import annotations

import struct
import sys

import pytest

from g2lex.membership import (
    BloomMembership,
    DafsaBinaryMembership,
    MarisaMembership,
    MembershipIndex,
    MPHMembership,
    SortedUTF8Membership,
)


def test_membership_index_forms_and_word_count_modes() -> None:
    index = MembershipIndex.from_words(["a", "ab", "你好"])
    assert index.word_count == 3
    value = index.as_dict()
    assert MembershipIndex.from_dict(value).iter_words() == index.iter_words()
    value.pop("word_count")
    assert MembershipIndex.from_dict(value).word_count == 3
    with pytest.raises(ValueError, match="unsupported"):
        MembershipIndex.from_dict({**index.as_dict(), "version": 99})
    with pytest.raises(ValueError, match="different lengths"):
        MembershipIndex.from_dict({"edges": [], "terminal_states": [True]})
    assert index.prefixes("abx") == ("a", "ab")
    assert index.prefixes("x") == ()


def test_sorted_utf8_roundtrip_cache_prefixes_and_corruption() -> None:
    backend = SortedUTF8Membership.from_words(["alpha", "alpine", "beta", "é"])
    first = backend.serialize()
    assert backend.serialize() is first
    restored = SortedUTF8Membership.deserialize(first)
    assert tuple(restored.iter_words()) == ("alpha", "alpine", "beta", "é")
    assert restored.contains("é") and not restored.contains("missing")
    assert restored.prefixes("alpinex") == ("alpine",)
    assert restored.prefixes("z") == ()
    assert restored.prefixes("") == ()
    for payload, message in (
        (b"bad!" + b"\x00" * 8, "header"),
        (struct.pack("<4sII", b"SUTF", 2, 0), "unsupported"),
        (first[:15], "offsets"),
        (first[:12] + struct.pack("<5I", 0, 100, 1, 2, 3) + first[32:], "offsets"),
    ):
        with pytest.raises(ValueError, match=message):
            SortedUTF8Membership.deserialize(payload)

    # A correct table with a non-UTF-8 pool is rejected after offsets parse.
    bad = bytearray(first)
    bad[-1] = 0xFF
    with pytest.raises(ValueError, match="word pool"):
        SortedUTF8Membership.deserialize(bad)


def _dafsa_layout(raw: bytes) -> tuple[int, int, int, int]:
    _magic, _version, _root, states, edges = struct.unpack_from("<4sIIII", raw)
    terminals = 20
    states_at = terminals + states
    edges_at = states_at + states * 8
    return states, edges, states_at, edges_at


def test_binary_dafsa_corruption_matrix() -> None:
    backend = DafsaBinaryMembership.from_words(["a", "ab", "b", "é"])
    raw = backend.serialize()
    restored = DafsaBinaryMembership.deserialize(raw)
    assert restored.contains("ab") and not restored.contains("ac")
    states, edges, states_at, edges_at = _dafsa_layout(raw)

    for payload, message in ((b"bad!" + raw[4:], "header"), (raw[:20], "arrays")):
        with pytest.raises(ValueError, match=message):
            DafsaBinaryMembership.deserialize(payload)
    candidate = bytearray(raw)
    struct.pack_into("<I", candidate, 4, 1)
    with pytest.raises(ValueError, match="unsupported"):
        DafsaBinaryMembership.deserialize(candidate)
    candidate = bytearray(raw)
    struct.pack_into("<I", candidate, 8, states + 1)
    with pytest.raises(ValueError, match="root"):
        DafsaBinaryMembership.deserialize(candidate)

    # State edge range outside the edge table.
    candidate = bytearray(raw)
    struct.pack_into("<I", candidate, states_at + 4, edges + 1)
    with pytest.raises(ValueError, match="edge range"):
        DafsaBinaryMembership.deserialize(candidate)
    # Edge label range and target state are independent checks.
    candidate = bytearray(raw)
    struct.pack_into("<I", candidate, edges_at, 10_000)
    with pytest.raises(ValueError, match="edge is invalid"):
        DafsaBinaryMembership.deserialize(candidate)
    candidate = bytearray(raw)
    struct.pack_into("<I", candidate, edges_at + 8, states + 1)
    with pytest.raises(ValueError, match="edge is invalid"):
        DafsaBinaryMembership.deserialize(candidate)

    # The first edge is one codepoint; make it span two codepoints.
    candidate = bytearray(raw)
    struct.pack_into("<I", candidate, edges_at + 4, 2)
    with pytest.raises(ValueError, match="one codepoint"):
        DafsaBinaryMembership.deserialize(candidate)
    candidate = bytearray(raw)
    pool_at = edges_at + edges * 16
    candidate[pool_at] = 0xFF
    with pytest.raises(ValueError, match="UTF-8"):
        DafsaBinaryMembership.deserialize(candidate)


def test_bloom_is_exact_and_roundtrips() -> None:
    exact = DafsaBinaryMembership.from_words(["alpha", "beta"])
    bloom = BloomMembership(exact, bits_per_key=8, hash_count=2, seed=7)
    assert bloom.contains("alpha")
    assert not bloom.contains("absent")
    assert tuple(bloom.iter_words()) == tuple(exact.iter_words())
    assert bloom.prefixes("alphax") == ("alpha",)
    assert bloom.word_count == 2
    assert bloom.serialized_bytes > len(bloom.serialize())
    assert bloom.serialize_sections().keys() == {"membership.bloom", "membership.bloom-exact"}
    restored = BloomMembership.deserialize(bloom.serialize(), exact)
    assert restored.contains("beta") and not restored.contains("gamma")

    # Even if the filter says yes, the exact backend remains authoritative.
    bloom._bits[:] = b"\xff" * len(bloom._bits)
    assert not bloom.contains("definitely-not-present")
    with pytest.raises(ValueError, match="positive"):
        BloomMembership(exact, bits_per_key=0)
    with pytest.raises(ValueError, match="positive"):
        BloomMembership(exact, hash_count=0)
    with pytest.raises(ValueError, match="header"):
        BloomMembership.deserialize(b"bad!" + b"\x00" * 20, exact)
    with pytest.raises(ValueError, match="bit array"):
        BloomMembership.deserialize(bloom.serialize()[:20], exact)
    invalid = bytearray(bloom.serialize())
    struct.pack_into("<I", invalid, 16, 64)
    with pytest.raises(ValueError, match="bit array"):
        BloomMembership.deserialize(invalid, exact)


def test_mph_empty_and_fallback_lookup() -> None:
    empty = MPHMembership.from_words([])
    assert not empty.contains("anything")
    backend = MPHMembership.from_words(["alpha", "beta"])
    assert backend.contains("alpha") and backend.contains("beta")
    assert not backend.contains("gamma")
    assert backend.serialize_sections().keys() == {"membership.mph"}


def test_optional_marisa_dependency_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "marisa_trie", None)
    with pytest.raises(ImportError, match="marisa-trie"):
        MarisaMembership(["word"])
