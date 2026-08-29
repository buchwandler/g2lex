from __future__ import annotations

import zlib
from contextlib import contextmanager
from pathlib import Path

import pytest

from g2lex import WORD_ONLY, TaggedValue, open_bytes, open_traversable
from g2lex.format import BinaryLexiconContainer, pack_typed
from g2lex.lexicon import Lexicon, LexiconRecord, open_lexicon


def _lexicon(entries: dict[str, object], *, cache_size: int = 8) -> Lexicon:
    data = pack_typed(entries, record_block_entries=1, compression="none")  # type: ignore[arg-type]
    return Lexicon(BinaryLexiconContainer(data), cache_size=cache_size)


def test_lexicon_record_facade_variants_and_equality() -> None:
    records = [
        LexiconRecord(TaggedValue((("DEFAULT", "x"),))),
        LexiconRecord("x"),
        LexiconRecord(("x", "y")),
        LexiconRecord(WORD_ONLY),
    ]
    assert [record.kind for record in records] == ["tagged", "string", "string_list", "word_only"]
    assert records[0].tagged_items() == (("DEFAULT", "x"),)
    assert records[1].tagged_items() == ()
    assert records[1] == LexiconRecord("x") == "x"
    assert records[1] != "y"
    assert repr(records[1]) == "LexiconRecord('x')"


def test_cache_is_bounded_and_lru_order_changes() -> None:
    lexicon = _lexicon({str(i): str(i) for i in range(4)}, cache_size=2)
    try:
        assert lexicon._cache_size == 2
        assert lexicon["0"] == "0"
        assert lexicon["1"] == "1"
        assert list(lexicon._blocks) == [0, 1]
        assert lexicon["0"] == "0"
        assert list(lexicon._blocks) == [1, 0]
        assert lexicon["2"] == "2"
        assert list(lexicon._blocks) == [0, 2]
        assert len(lexicon._blocks) <= 2
    finally:
        lexicon.close()

    zero = _lexicon({"a": "x", "b": "y"}, cache_size=0)
    try:
        assert zero._cache_size == 1
        assert zero["a"] == "x"
    finally:
        zero.close()


def test_mapping_select_iteration_and_missing_behavior() -> None:
    lexicon = _lexicon(
        {
            "plain": "p",
            "tagged": TaggedValue((("ALT", "a"), ("DEFAULT", "d"))),
            "only-default": TaggedValue((("DEFAULT", "d"),)),
            "none": TaggedValue((("ALT", None),)),
        }
    )
    try:
        assert lexicon.get_record("plain") == "p"
        with pytest.raises(KeyError):
            lexicon.get_record("missing")
        assert lexicon.get("missing", "fallback") == "fallback"
        assert "missing" not in lexicon
        assert 42 not in lexicon  # type: ignore[operator]
        assert list(lexicon) == sorted(lexicon)
        assert len(lexicon) == 4
        assert lexicon.select("missing", missing="fallback") == "fallback"
        assert lexicon.select("plain", "ALT") == "p"
        assert lexicon.select("tagged", "ALT") == "a"
        assert lexicon.select("tagged", "MISSING") == "d"
        assert lexicon.select("only-default", "MISSING") == "d"
        assert lexicon.select("none", "MISSING", missing="missing") == "missing"
    finally:
        lexicon.close()


def test_corrupt_runtime_blocks_are_rejected() -> None:
    data = bytearray(pack_typed({"a": "x", "b": "y"}, record_block_entries=1, compression="none"))
    container = BinaryLexiconContainer(data)
    records_offset = container._sections["records.blocks"][0]
    records_dir = container.record_descriptors

    # Checksum failure after the container has already validated its TOC.
    data[records_offset + records_dir[0][0] + records_dir[0][1] - 1] ^= 1
    lexicon = Lexicon(container)
    try:
        with pytest.raises(ValueError, match="checksum"):
            lexicon["a"]
    finally:
        lexicon.close()

    # Runtime record-directory checks operate on the decoded raw block.
    for mutate, message in (
        (lambda block: block.__setitem__(slice(0, 4), b"\x00\x00\x00\x02"), "offsets"),
        (lambda block: block.__setitem__(slice(4, 8), b"\x00\x00\x00\x08"), "offset"),
    ):
        candidate = bytearray(pack_typed({"a": "x"}, record_block_entries=1, compression="none"))
        parsed = BinaryLexiconContainer(candidate)
        section_offset = parsed._sections["records.blocks"][0]
        descriptor = parsed.record_descriptors[0]
        block = memoryview(candidate)[
            section_offset + descriptor[0] : section_offset + descriptor[0] + descriptor[1]
        ]
        mutate(block)
        parsed.record_descriptors = (descriptor[:4] + (zlib.crc32(block) & 0xFFFFFFFF,),)
        runtime = Lexicon(parsed)
        try:
            with pytest.raises(ValueError, match=message):
                runtime["a"]
        finally:
            runtime.close()


def test_close_is_idempotent_and_all_operations_reject_closed() -> None:
    lexicon = _lexicon({"a": "x"})
    lexicon.close()
    lexicon.close()
    operations = (
        lambda: lexicon.get_record("a"),
        lambda: lexicon["a"],
        lambda: lexicon.get("a"),
        lambda: "a" in lexicon,
        lambda: iter(lexicon),
        lambda: len(lexicon),
        lambda: lexicon.select("a"),
    )
    for operation in operations:
        with pytest.raises(ValueError, match="closed|released"):
            operation()
    with pytest.raises(ValueError, match="closed"):
        lexicon.__enter__()


def test_open_bytes_context_and_mmap_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = pack_typed({"word": "wɜːd"})
    with open_bytes(memoryview(raw)) as lexicon:
        assert lexicon["word"] == "wɜːd"
    path = tmp_path / "broken.g2lex"
    path.write_bytes(raw[:10])
    with pytest.raises(ValueError):
        open_lexicon(path)


def test_open_traversable_paths_fallback_and_exception_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = pack_typed({"word": "value"})
    path = tmp_path / "word.g2lex"
    path.write_bytes(raw)
    path_lexicon = open_traversable(path)
    try:
        assert path_lexicon["word"] == "value"
    finally:
        path_lexicon.close()

    class Fspath:
        def __fspath__(self) -> str:
            return str(path)

    fspath_lexicon = open_traversable(Fspath())
    try:
        assert fspath_lexicon["word"] == "value"
    finally:
        fspath_lexicon.close()

    class Resource:
        def read_bytes(self) -> bytes:
            return raw

    resource_lexicon = open_traversable(Resource())
    try:
        assert resource_lexicon["word"] == "value"
    finally:
        resource_lexicon.close()

    closed = False

    @contextmanager
    def fake_as_file(_resource: object):
        nonlocal closed
        try:
            yield path
        finally:
            closed = True

    monkeypatch.setattr("importlib.resources.as_file", fake_as_file)

    def fail(_path: Path) -> Lexicon:
        raise RuntimeError("open failed")

    monkeypatch.setattr("g2lex.lexicon._open_mmap", fail)
    with pytest.raises(RuntimeError, match="open failed"):
        open_traversable(object())
    assert closed
