"""Lazy runtime mapping for G2Lex v1 files."""

from __future__ import annotations

import mmap
import struct
from collections import OrderedDict
from collections.abc import Iterator, Mapping
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from .format import BinaryLexiconContainer
from .record_store import decode_record, decompress_block
from .value import LexiconValue, TaggedValue


class LexiconRecord:
    """Small typed record facade that defers materialization of selector maps."""

    __slots__ = ("value",)

    def __init__(self, value: LexiconValue):
        self.value = value

    @property
    def kind(self) -> str:
        if isinstance(self.value, TaggedValue):
            return "tagged"
        if isinstance(self.value, str):
            return "string"
        if isinstance(self.value, tuple):
            return "string_list"
        return "word_only"

    def tagged_items(self):
        if not isinstance(self.value, TaggedValue):
            return ()
        return self.value.items

    def __eq__(self, other: object) -> bool:
        return self.value == (other.value if isinstance(other, LexiconRecord) else other)

    def __repr__(self) -> str:
        return f"LexiconRecord({self.value!r})"


class Lexicon(Mapping[str, LexiconValue]):
    """Immutable mapping whose keys and values are decoded on demand."""

    def __init__(
        self, container: BinaryLexiconContainer, *, owner: Any = None, cache_size: int = 8
    ):
        self._container = container
        self._owner = owner
        self._cache_size = max(1, cache_size)
        self._blocks: OrderedDict[int, bytes] = OrderedDict()
        self._closed = False
        self._codec = str(container.manifest["record_codec"]).removesuffix("-block-v1")
        self.metadata = container.manifest
        self.source = container.manifest.get("source", {})

    def _ensure_open(self) -> None:
        if self._closed:
            raise ValueError("lexicon is closed")

    def _block(self, block_number: int) -> bytes:
        self._ensure_open()
        cached = self._blocks.get(block_number)
        if cached is not None:
            self._blocks.move_to_end(block_number)
            return cached
        offset, stored_size, raw_size, _count, checksum = self._container.record_descriptors[
            block_number
        ]
        stored = self._container.section_view("records.blocks")[offset : offset + stored_size]
        raw = decompress_block(stored, self._codec, raw_size)
        import zlib

        if zlib.crc32(raw) & 0xFFFFFFFF != checksum:
            raise ValueError("record block checksum mismatch")
        self._blocks[block_number] = raw
        self._blocks.move_to_end(block_number)
        while len(self._blocks) > self._cache_size:
            self._blocks.popitem(last=False)
        return raw

    def _value_at(self, ordinal: int) -> LexiconValue:
        block_number = ordinal // self._container.record_block_entries
        local = ordinal % self._container.record_block_entries
        block = self._block(block_number)
        if len(block) < 8:
            raise ValueError("truncated record block")
        count = struct.unpack_from(">I", block)[0]
        if local >= count:
            raise ValueError("record directory and block count mismatch")
        table_end = 4 + 4 * (count + 1)
        if table_end > len(block):
            raise ValueError("truncated record block offsets")
        start = struct.unpack_from(">I", block, 4 + local * 4)[0]
        end = struct.unpack_from(">I", block, 4 + (local + 1) * 4)[0]
        payload_start = table_end
        if start > end or payload_start + end > len(block):
            raise ValueError("invalid record block offset")
        return decode_record(
            block[payload_start + start : payload_start + end], self._container.tags
        )

    def get_record(self, word: str) -> LexiconRecord:
        ordinal = self._container.key_index.find(word)
        if ordinal is None:
            raise KeyError(word)
        return LexiconRecord(self._value_at(ordinal))

    def __getitem__(self, word: str) -> LexiconValue:
        return self.get_record(word).value

    def get(self, word: str, default: Any = None) -> LexiconValue | Any:
        self._ensure_open()
        ordinal = self._container.key_index.find(word)
        return default if ordinal is None else self._value_at(ordinal)

    def __contains__(self, word: object) -> bool:
        self._ensure_open()
        return isinstance(word, str) and self._container.key_index.find(word) is not None

    def __iter__(self) -> Iterator[str]:
        self._ensure_open()
        return iter(self._container.key_index)

    def __len__(self) -> int:
        self._ensure_open()
        return self._container.record_count

    def select(
        self,
        word: str,
        tag: str | None = None,
        default_tag: str = "DEFAULT",
        missing: Any = None,
    ) -> Any:
        value = self.get(word, missing)
        if value is missing:
            return missing
        if not isinstance(value, TaggedValue):
            return value
        if tag is not None and tag in value:
            return value[tag]
        if default_tag in value:
            return value[default_tag]
        return missing

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._blocks.clear()
        key_view = getattr(self._container.key_index, "_view", None)
        if key_view is not None:
            key_view.release()
        self._container._view.release()
        if self._owner is not None:
            self._owner.close()
            self._owner = None

    def __enter__(self) -> Lexicon:  # noqa: PYI034
        self._ensure_open()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


def _open_mmap(path: Path) -> Lexicon:
    handle = path.open("rb")
    mapped = None
    try:
        mapped = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
        container = BinaryLexiconContainer(memoryview(mapped))
    except Exception as exc:
        if mapped is not None:
            import traceback

            traceback.clear_frames(exc.__traceback__)
            mapped.close()
        handle.close()
        raise

    assert mapped is not None
    mapped_owner = mapped

    class _Owner:
        def close(self) -> None:
            mapped_owner.close()
            handle.close()

    return Lexicon(container, owner=_Owner())


def open_lexicon(path: str | Path) -> Lexicon:
    return _open_mmap(Path(path))


open = open_lexicon


def open_bytes(data: bytes | bytearray | memoryview) -> Lexicon:
    return Lexicon(BinaryLexiconContainer(data))


def open_traversable(resource: Any) -> Lexicon:
    """Open a package resource while retaining any temporary extraction lifetime."""
    if isinstance(resource, (str, Path)):
        return open_lexicon(resource)
    path = getattr(resource, "__fspath__", None)
    if path is not None:
        return open_lexicon(path())

    stack = ExitStack()
    try:
        from importlib.resources import as_file

        path = stack.enter_context(as_file(resource))
        lexicon = _open_mmap(Path(path))
    except (TypeError, FileNotFoundError, AttributeError):
        stack.close()
        return open_bytes(resource.read_bytes())
    except Exception:
        stack.close()
        raise

    original_close = lexicon.close

    def close() -> None:
        original_close()
        stack.close()

    lexicon.close = close  # type: ignore[method-assign]
    return lexicon
