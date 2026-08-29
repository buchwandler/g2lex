from __future__ import annotations

import json
from pathlib import Path

import pytest

from g2lex import WORD_ONLY, TaggedValue, open_bytes
from g2lex.format import pack_typed
from g2lex.operations import convert_file, export_file, pack_file


def _source(path: Path, payload: object | None = None) -> None:
    path.write_text(json.dumps(payload or {"a": "x", "b": ["y", "z"]}), encoding="utf-8")


def test_pack_file_self_verification_and_atomic_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.json"
    _source(source)
    destination = tmp_path / "out.g2lex"
    destination.write_bytes(b"old")
    monkeypatch.setattr("g2lex.operations.verify_typed", lambda *_: {"lossless": False})
    with pytest.raises(ValueError, match="self-verification"):
        pack_file(source, destination)
    assert destination.read_bytes() == b"old"

    monkeypatch.undo()
    original_replace = __import__("os").replace

    def fail_replace(_temporary: str, _destination: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("g2lex.operations.os.replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        pack_file(source, destination)
    assert destination.read_bytes() == b"old"
    assert not list(tmp_path.glob(".out.g2lex.*"))
    monkeypatch.setattr("g2lex.operations.os.replace", original_replace)


def test_export_all_shapes_formats_lossy_and_ownership(tmp_path: Path) -> None:
    entries = {
        "scalar": "x",
        "list": ("y", "z"),
        "tagged": TaggedValue((("DEFAULT", "d"), ("ALT", None))),
        "word": WORD_ONLY,
    }
    asset = tmp_path / "asset.g2lex"
    asset.write_bytes(pack_typed(entries))

    with pytest.raises(ValueError, match="JSON maps"):
        export_file(asset, tmp_path / "bad.json", format="json")
    with pytest.raises(ValueError, match="legacy TSV"):
        export_file(asset, tmp_path / "bad.tsv", format="tsv")
    export_file(asset, tmp_path / "lossy.tsv", format="tsv", allow_lossy=True)
    assert "scalar\tx" in (tmp_path / "lossy.tsv").read_text()
    export_file(asset, tmp_path / "extended.tsv", format="lxc-tsv")
    assert "tagged" in (tmp_path / "extended.tsv").read_text()
    export_file(asset, tmp_path / "values.jsonl", format="jsonl")
    assert '"kind":"word"' in (tmp_path / "values.jsonl").read_text()
    with pytest.raises(ValueError, match="membership-only"):
        export_file(asset, tmp_path / "words.txt", format="words")
    export_file(asset, tmp_path / "words.txt", format="words", allow_lossy=True)

    # Auto suffix selection exercises JSON, JSONL, words, and the TSV default.
    simple = tmp_path / "simple.g2lex"
    simple.write_bytes(pack_typed({"a": "x"}))
    for suffix in (".json", ".jsonl", ".tsv"):
        output = tmp_path / ("auto" + suffix)
        export_file(simple, output)
        assert output.exists() and output.read_text()
    word_asset = tmp_path / "word-only.g2lex"
    word_asset.write_bytes(pack_typed({"a": WORD_ONLY}))
    output = tmp_path / "auto.txt"
    export_file(word_asset, output)
    assert output.read_text() == "a\n"

    borrowed = open_bytes(pack_typed({"a": "x"}))
    export_file(borrowed, tmp_path / "borrowed.jsonl")
    assert borrowed["a"] == "x"
    borrowed.close()


def test_convert_source_detection_and_output_branches(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    _source(source, {"a": "x", "b": ["y", "z"]})
    for suffix in (".json", ".jsonl", ".tsv", ".lxc-tsv"):
        output = tmp_path / ("converted" + suffix)
        convert_file(source, output)
        assert output.exists() and output.read_text()

    word_source = tmp_path / "words.txt"
    word_source.write_text("a\nb\n", encoding="utf-8")
    convert_file(word_source, tmp_path / "words.jsonl", input_format="words", output_format="jsonl")
    assert json.loads((tmp_path / "words.jsonl").read_text().splitlines()[0])["kind"] == "word"
    with pytest.raises(ValueError, match="membership-only"):
        convert_file(source, tmp_path / "bad.txt", output_format="words")
    convert_file(source, tmp_path / "lossy.txt", output_format="words", allow_lossy=True)

    packed = tmp_path / "source.g2lex"
    packed.write_bytes(pack_typed({"a": "x"}))
    target = tmp_path / "from-g2lex.jsonl"
    convert_file(packed, target)
    assert target.read_text()


def test_export_open_asset_is_closed_but_borrowed_is_not(tmp_path: Path) -> None:
    path = tmp_path / "asset.g2lex"
    path.write_bytes(pack_typed({"a": "x"}))
    export_file(path, tmp_path / "out.jsonl")
    # The owned lexicon is internal; opening a fresh one proves the asset remains usable.
    borrowed = open_bytes(path.read_bytes())
    export_file(borrowed, tmp_path / "out2.jsonl")
    assert borrowed["a"] == "x"
    borrowed.close()
