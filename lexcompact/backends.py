"""Central factories for benchmark-selectable runtime backends."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .literals import (
    BinaryPoolLiteralStore,
    LiteralLexicon,
    RePairCodec,
    SymbolCodec,
    TokenSpacedCodec,
)
from .membership import BloomMembership, DafsaBinaryMembership, MembershipIndex, SortedUTF8Membership

MEMBERSHIP_BACKENDS = (
    "dafsa-json-v1",
    "dafsa-binary-v2",
    "sorted-utf8",
    "bloom+dafsa-binary-v2",
)
LITERAL_BACKENDS = ("dict-json-v3", "binary-pool-v2")
CODECS = ("utf8", "repair", "symbol-u8", "symbol-u16", "token-spaced")


def supported_backend_names() -> dict[str, tuple[str, ...]]:
    return {
        "membership": MEMBERSHIP_BACKENDS,
        "literal": LITERAL_BACKENDS,
        "codec": CODECS,
    }


def build_membership_backend(
    name: str,
    words: Iterable[str],
    *,
    seed: int = 0,
    **options: Any,
):
    values = tuple(words)
    if name == "dafsa-json-v1":
        return MembershipIndex.from_words(values)
    if name == "dafsa-binary-v2":
        return DafsaBinaryMembership.from_words(values)
    if name == "sorted-utf8":
        return SortedUTF8Membership.from_words(values)
    if name == "bloom+dafsa-binary-v2":
        exact = DafsaBinaryMembership.from_words(values)
        return BloomMembership(
            exact,
            bits_per_key=int(options.get("bits_per_key", 10)),
            hash_count=int(options.get("hash_count", 3)),
            seed=seed,
        )
    raise ValueError(f"unknown membership backend: {name}")


def build_literal_store(
    name: str,
    literals: Mapping[str, Iterable[str]],
    *,
    codec: Any | None = None,
    **options: Any,
):
    if name == "dict-json-v3":
        return LiteralLexicon(literals)
    if name == "binary-pool-v2":
        return BinaryPoolLiteralStore(literals)
    raise ValueError(f"unknown literal backend: {name}")


def build_codec(name: str, values: Iterable[str] = (), *, max_pairs: int = 64, **options: Any):
    if name == "utf8":
        return None
    if name == "repair":
        return RePairCodec(max_pairs=max_pairs)
    inventory = tuple(values)
    if name in {"symbol-u8", "symbol-u16"}:
        codec = SymbolCodec(inventory)
        expected = 1 if name == "symbol-u8" else 2
        if codec.width != expected:
            raise ValueError(f"codec {name} does not match its symbol inventory")
        return codec
    if name == "token-spaced":
        return TokenSpacedCodec(inventory)
    raise ValueError(f"unknown pronunciation codec: {name}")


__all__ = [
    "CODECS",
    "LITERAL_BACKENDS",
    "MEMBERSHIP_BACKENDS",
    "build_codec",
    "build_literal_store",
    "build_membership_backend",
    "supported_backend_names",
]
