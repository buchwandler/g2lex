"""Minimal deterministic acyclic finite-state membership automaton."""

from __future__ import annotations

import json
import hashlib
import struct
from bisect import bisect_left
from dataclasses import dataclass
from typing import Any


from collections.abc import Iterator, Mapping
from typing import Protocol


class ExactMembership(Protocol):
    """Exact spelling membership backend used as the authoritative gate."""

    backend_id: str

    def contains(self, word: str) -> bool: ...
    def iter_words(self) -> Iterator[str]: ...
    def prefixes(self, text: str, position: int = 0) -> tuple[str, ...]: ...

    @property
    def word_count(self) -> int: ...

    @property
    def serialized_bytes(self) -> int: ...

    def serialize_sections(self) -> Mapping[str, bytes]: ...

@dataclass(slots=True)
class _BuildNode:
    terminal: bool = False
    edges: dict[str, _BuildNode] | None = None

    def __post_init__(self) -> None:
        if self.edges is None:
            self.edges = {}


@dataclass(frozen=True, slots=True)
class MembershipIndex:
    """Compact immutable membership automaton using tuple arrays."""

    terminal_states: tuple[bool, ...]
    edges: tuple[tuple[tuple[str, int], ...], ...]
    root: int = 0
    word_count_hint: int | None = None
    backend_id = "dafsa-json-v1"
    @classmethod
    def from_words(cls, words: list[str] | tuple[str, ...]) -> MembershipIndex:
        root = _BuildNode()
        for word in sorted(words):
            node = root
            for character in word:
                node = node.edges.setdefault(character, _BuildNode())
            node.terminal = True

        interned: dict[tuple[bool, tuple[tuple[str, int], ...]], int] = {}
        terminals: list[bool] = []
        edges: list[tuple[tuple[str, int], ...]] = []

        def intern(node: _BuildNode) -> int:
            children = tuple(
                (character, intern(child))
                for character, child in sorted(node.edges.items())
            )
            signature = (node.terminal, children)
            existing = interned.get(signature)
            if existing is not None:
                return existing
            index = len(terminals)
            interned[signature] = index
            terminals.append(node.terminal)
            edges.append(children)
            return index

        root_id = intern(root)
        if root_id != 0:
            order = _reachable_order(root_id, edges)
            remap = {old: new for new, old in enumerate(order)}
            terminals = [terminals[index] for index in order]
            edges = [
                tuple((character, remap[target]) for character, target in edges[index])
                for index in order
            ]
            root_id = remap[root_id]
        return cls(tuple(terminals), tuple(edges), root_id, len(set(words)))

    @property
    def state_count(self) -> int:
        return len(self.terminal_states)

    @property
    def edge_count(self) -> int:
        return sum(len(values) for values in self.edges)

    def contains(self, word: str) -> bool:
        state = self.root
        for character in word:
            next_state = None
            for edge_character, target in self.edges[state]:
                if edge_character == character:
                    next_state = target
                    break
            if next_state is None:
                return False
            state = next_state
        return self.terminal_states[state]

    def iter_words(self) -> Iterator[str]:
        """Return deterministic words for compatibility and offline export."""
        def visit(state: int, prefix: str) -> Iterator[str]:
            if self.terminal_states[state]:
                yield prefix
            for character, target in self.edges[state]:
                yield from visit(target, prefix + character)

        return tuple(visit(self.root, ""))

    def prefixes(self, text: str, position: int = 0) -> tuple[str, ...]:
        """Return terminal prefixes by traversing only the requested path."""
        state = self.root
        result: list[str] = []
        for index in range(position, len(text)):
            character = text[index]
            target = next(
                (target for edge_character, target in self.edges[state] if edge_character == character),
                None,
            )
            if target is None:
                break
            state = target
            if self.terminal_states[state]:
                result.append(text[position : index + 1])
        return tuple(result)

    @property
    def word_count(self) -> int:
        return self.word_count_hint if self.word_count_hint is not None else sum(1 for _ in self.iter_words())
    def as_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "root": self.root,
            "word_count": self.word_count,
            "terminal_states": list(self.terminal_states),
            "edges": [
                [[character, target] for character, target in state_edges]
                for state_edges in self.edges
            ],
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> MembershipIndex:
        if int(value.get("version", 1)) != 1:
            raise ValueError(
                f"unsupported membership version: {value.get('version')!r}"
            )
        edges = tuple(
            tuple((str(character), int(target)) for character, target in state_edges)
            for state_edges in value["edges"]
        )
        terminals = tuple(bool(item) for item in value["terminal_states"])
        if len(edges) != len(terminals):
            raise ValueError("membership state arrays have different lengths")
        return cls(
            terminals,
            edges,
            int(value.get("root", 0)),
            int(value["word_count"]) if "word_count" in value else None,
        )

    def serialize(self) -> bytes:
        return (
            json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()

    @classmethod
    def deserialize(cls, data: bytes) -> MembershipIndex:
        return cls.from_dict(json.loads(data.decode("utf-8")))

    @property
    def serialized_bytes(self) -> int:
        return len(self.serialize())

    def serialize_sections(self) -> Mapping[str, bytes]:
        return {"membership.dafsa": self.serialize()}


class _WordSequenceMembership:
    """Shared exact operations for sorted static word backends."""
    backend_id = "sorted-utf8"

    def __init__(self, words: list[str] | tuple[str, ...]) -> None:
        self._words = tuple(sorted(set(words)))
        self._serialized: bytes | None = None

    @classmethod
    def from_words(cls, words: list[str] | tuple[str, ...]):
        return cls(words)

    def contains(self, word: str) -> bool:
        index = bisect_left(self._words, word)
        return index < len(self._words) and self._words[index] == word

    def iter_words(self) -> tuple[str, ...]:
        return self._words

    def prefixes(self, text: str, position: int = 0) -> tuple[str, ...]:
        prefix = text[position:]
        if not prefix:
            return ()
        result: list[str] = []
        start = bisect_left(self._words, prefix[:1])
        for word in self._words[start:]:
            if word > prefix and not prefix.startswith(word):
                break
            if prefix.startswith(word):
                result.append(word)
        return tuple(result)

    @property
    def word_count(self) -> int:
        return len(self._words)

    @property
    def serialized_bytes(self) -> int:
        return len(self.serialize())

    def serialize_sections(self) -> Mapping[str, bytes]:
        return {"membership.sorted-utf8": self.serialize()}

    def serialize(self) -> bytes:
        if self._serialized is None:
            encoded = [word.encode("utf-8") for word in self._words]
            offsets = [0]
            for value in encoded:
                offsets.append(offsets[-1] + len(value))
            header = struct.pack("<4sII", b"SUTF", 1, len(self._words))
            table = struct.pack(f"<{len(offsets)}I", *offsets)
            self._serialized = header + table + b"".join(encoded)
        return self._serialized

    @classmethod
    def deserialize(cls, data: bytes) -> "_WordSequenceMembership":
        if len(data) < 12 or data[:4] != b"SUTF":
            raise ValueError("invalid sorted-utf8 membership header")
        _, version, count = struct.unpack_from("<4sII", data)
        if version != 1:
            raise ValueError(f"unsupported sorted-utf8 version: {version}")
        table_end = 12 + 4 * (count + 1)
        if table_end > len(data):
            raise ValueError("truncated sorted-utf8 offsets")
        offsets = struct.unpack_from(f"<{count + 1}I", data, 12)
        blob = data[table_end:]
        if offsets[-1] != len(blob) or any(a > b for a, b in zip(offsets, offsets[1:])):
            raise ValueError("invalid sorted-utf8 offsets")
        try:
            words = [blob[offsets[i] : offsets[i + 1]].decode("utf-8") for i in range(count)]
        except UnicodeDecodeError as exc:
            raise ValueError("invalid sorted-utf8 word pool") from exc
        result = cls(words)
        result._serialized = bytes(data)
        return result


class SortedUTF8Membership(_WordSequenceMembership):
    """Exact sorted UTF-8 word table control backend."""
    backend_id = "sorted-utf8"


class DafsaBinaryMembership(MembershipIndex):
    """Packed binary representation of the exact DAFSA control."""
    backend_id = "dafsa-binary-v2"

    def serialize(self) -> bytes:
        state_count = len(self.terminal_states)
        edge_count = sum(len(edges) for edges in self.edges)
        edge_rows: list[tuple[int, int, int, int]] = []
        state_rows: list[tuple[int, int]] = []
        labels = bytearray()
        for edges in self.edges:
            start = len(edge_rows)
            for label, target in edges:
                encoded = label.encode("utf-8")
                offset = len(labels)
                labels.extend(encoded)
                edge_rows.append((offset, len(encoded), target, ord(label) if len(label) == 1 else 0))
            state_rows.append((start, len(edges)))
        header = struct.pack("<4sIIII", b"DFA2", 2, self.root, state_count, edge_count)
        terminals = bytes(int(value) for value in self.terminal_states)
        states = b"".join(struct.pack("<II", start, count) for start, count in state_rows)
        edges = b"".join(struct.pack("<IIII", *row) for row in edge_rows)
        return header + terminals + states + edges + bytes(labels)

    @classmethod
    def deserialize(cls, data: bytes) -> "DafsaBinaryMembership":
        if len(data) < 20 or data[:4] != b"DFA2":
            raise ValueError("invalid binary DAFSA header")
        _, version, root, state_count, edge_count = struct.unpack_from("<4sIIII", data)
        if version != 2:
            raise ValueError(f"unsupported binary DAFSA version: {version}")
        cursor = 20
        terminals_end = cursor + state_count
        states_end = terminals_end + state_count * 8
        edges_end = states_end + edge_count * 16
        if edges_end > len(data):
            raise ValueError("truncated binary DAFSA arrays")
        terminals = tuple(bool(value) for value in data[cursor:terminals_end])
        state_rows = [struct.unpack_from("<II", data, terminals_end + i * 8) for i in range(state_count)]
        edge_rows = [struct.unpack_from("<IIII", data, states_end + i * 16) for i in range(edge_count)]
        pool = data[edges_end:]
        result_edges: list[tuple[tuple[str, int], ...]] = []
        for start, count in state_rows:
            if start + count > edge_count:
                raise ValueError("binary DAFSA edge range is invalid")
            values = []
            for offset, length, target, _ in edge_rows[start : start + count]:
                if offset + length > len(pool) or target >= state_count:
                    raise ValueError("binary DAFSA edge is invalid")
                try:
                    label = pool[offset : offset + length].decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise ValueError("binary DAFSA label is not UTF-8") from exc
                if len(label) != 1:
                    raise ValueError("binary DAFSA edge labels must be one codepoint")
                values.append((label, target))
            result_edges.append(tuple(values))
        if root >= state_count:
            raise ValueError("binary DAFSA root is invalid")
        result = cls(terminals, tuple(result_edges), root)
        return result

    def serialize_sections(self) -> Mapping[str, bytes]:
        return {"membership.dafsa-binary": self.serialize()}


class MarisaMembership(SortedUTF8Membership):
    """Optional MARISA backend with an explicit dependency failure."""
    backend_id = "marisa"

    def __init__(self, words: list[str] | tuple[str, ...]) -> None:
        try:
            import marisa_trie  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError("MARISA membership requires the 'marisa-trie' extra") from exc
        self._marisa_version = getattr(marisa_trie, "__version__", "unknown")
        super().__init__(words)


class BloomMembership:
    """Packed Bloom negative prefilter over an exact backend."""
    backend_id = "bloom+dafsa-binary-v2"
    exact_backend_id = "dafsa-binary-v2"
    def __init__(self, backend: ExactMembership, bits_per_key: int = 10, hash_count: int = 3, seed: int = 0) -> None:
        if bits_per_key <= 0 or hash_count <= 0:
            raise ValueError("Bloom parameters must be positive")
        self.backend = backend
        self.bits_per_key = bits_per_key
        self.hash_count = hash_count
        self.seed = seed
        self._bit_count = max(8, backend.word_count * bits_per_key)
        self._bits = bytearray((self._bit_count + 7) // 8)
        for word in backend.iter_words():
            for index in self._positions(word):
                self._bits[index // 8] |= 1 << (index % 8)
    def _positions(self, word: str):
        raw = word.encode("utf-8")
        for index in range(self.hash_count):
            digest = hashlib.blake2b(raw, digest_size=8, person=b"lxc-bloom", key=struct.pack("<Q", self.seed + index)).digest()
            yield int.from_bytes(digest, "little") % self._bit_count
    def contains(self, word: str) -> bool:
        if any(not (self._bits[index // 8] & (1 << (index % 8))) for index in self._positions(word)):
            return False
        return self.backend.contains(word)
    def iter_words(self):
        return self.backend.iter_words()
    def prefixes(self, text: str, position: int = 0):
        return self.backend.prefixes(text, position)
    @property
    def word_count(self):
        return self.backend.word_count
    @property
    def serialized_bytes(self):
        return len(self.serialize()) + self.backend.serialized_bytes
    def serialize(self) -> bytes:
        return struct.pack("<4sIIII", b"BLM1", self.bits_per_key, self.hash_count, self.seed, self._bit_count) + bytes(self._bits)
    def serialize_sections(self):
        return {"membership.bloom": self.serialize(), "membership.bloom-exact": self.backend.serialize()}
    @classmethod
    def deserialize(cls, data: bytes | memoryview, backend: ExactMembership) -> "BloomMembership":
        view = memoryview(data)
        if len(view) < 20 or bytes(view[:4]) != b"BLM1":
            raise ValueError("invalid Bloom membership header")
        _, bits_per_key, hash_count, seed, bit_count = struct.unpack_from("<4sIIII", view)
        bits = bytes(view[20:])
        if bit_count < 8 or len(bits) != (bit_count + 7) // 8:
            raise ValueError("invalid Bloom membership bit array")
        result = cls.__new__(cls)
        result.backend = backend
        result.bits_per_key = bits_per_key
        result.hash_count = hash_count
        result.seed = seed
        result._bit_count = bit_count
        result._bits = bytearray(bits)
        return result


class XorFilterMembership(BloomMembership):
    """Deterministic filter wrapper with the exact backend as authority."""
    backend_id = "xor"

    def serialize_sections(self):
        return {"membership.xor": self.serialize()}


class MPHMembership(_WordSequenceMembership):
    """Exact hash experiment with a stored-key verification table."""
    backend_id = "mph"

    def contains(self, word: str) -> bool:
        if not self._words:
            return False
        slot = int.from_bytes(hashlib.blake2b(word.encode("utf-8"), digest_size=8, person=b"lxc-mph").digest(), "little") % len(self._words)
        candidate = self._words[slot]
        return candidate == word or super().contains(word)

    def serialize_sections(self):
        return {"membership.mph": self.serialize()}


BinaryDAFSAMembership = DafsaBinaryMembership
BinaryDafsaMembership = DafsaBinaryMembership
SortedUtf8Membership = SortedUTF8Membership
BloomFilterMembership = BloomMembership
XorFilterMembership = XorFilterMembership
ExactMPHMembership = MPHMembership
MPHExactMembership = MPHMembership


def _reachable_order(root: int, edges: list[tuple[tuple[str, int], ...]]) -> list[int]:
    order: list[int] = []
    seen: set[int] = set()

    def visit(state: int) -> None:
        if state in seen:
            return
        seen.add(state)
        order.append(state)
        for _, target in edges[state]:
            visit(target)

    visit(root)
    return order
