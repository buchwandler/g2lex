from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from g2lex import open, open_bytes, open_traversable
from g2lex.format import BinaryLexiconContainer, pack_typed
from g2lex.record_store import MAX_RECORD_BLOCK_BYTES, decode_varint, decompress_block


class _Resource:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self.name = "resource.g2lex"

    def read_bytes(self) -> bytes:
        return self._data

    def is_dir(self) -> bool:
        return False


def test_bytes_memoryview_close_and_double_close() -> None:
    data = pack_typed({"word": "wɜːd"})
    for value in (data, memoryview(data)):
        lexicon = open_bytes(value)
        assert lexicon["word"] == "wɜːd"
        lexicon.close()
        lexicon.close()
        with pytest.raises(ValueError, match="closed"):
            lexicon.get("word")


def test_mmap_and_traversable_resource_lifetimes(tmp_path) -> None:
    data = pack_typed({"word": "wɜːd"})
    path = tmp_path / "word.g2lex"
    path.write_bytes(data)
    lexicon = open(path)
    assert lexicon.get("word") == "wɜːd"
    lexicon.close()
    resource = _Resource(data)
    lexicon = open_traversable(resource)
    try:
        assert lexicon["word"] == "wɜːd"
    finally:
        lexicon.close()


def test_concurrent_reads_are_exact() -> None:
    lexicon = open_bytes(pack_typed({str(index): str(index) for index in range(100)}))
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            values = list(pool.map(lambda word: lexicon[word], (str(i % 100) for i in range(1000))))
        assert values == [str(i % 100) for i in range(1000)]
    finally:
        lexicon.close()


def test_corrupt_headers_and_varints_are_rejected() -> None:
    data = bytearray(pack_typed({"word": "value"}))
    data[:4] = b"bad!"
    with pytest.raises(ValueError, match="magic"):
        BinaryLexiconContainer(data)
    with pytest.raises(ValueError, match="varint"):
        decode_varint(memoryview(b"\x80" * 10), 0, 10)


def test_decompression_bounds_and_trailing_data_are_rejected() -> None:
    with pytest.raises(ValueError, match="safety limit"):
        decompress_block(b"", "zlib", MAX_RECORD_BLOCK_BYTES + 1)
    import zlib

    compressed = zlib.compress(b"value") + b"trailing"
    with pytest.raises(ValueError, match="compressed record block"):
        decompress_block(compressed, "zlib", 5)
    with pytest.raises(ValueError, match="raw size"):
        decompress_block(zlib.compress(b"value"), "zlib", 6)
