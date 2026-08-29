from __future__ import annotations

import json
from pathlib import Path

import pytest

from g2lex import (
    WORD_ONLY,
    CaseAliasMapping,
    LayeredLexicon,
    LexiconLayer,
    SourceInfo,
    TaggedValue,
    TypedLexiconData,
    compare,
    open_bytes,
    pack_file,
)
from g2lex.adapters import (
    parse_extended_tsv_bytes,
    parse_jsonl_bytes,
    parse_kokoro_json_bytes,
    parse_word_list_bytes,
)
from g2lex.format import pack_typed


def test_typed_values_round_trip_and_selectors() -> None:
    entries = {
        "live": TaggedValue((("DEFAULT", "lˈIv"), ("VERB", "lˈɪv"))),
        "AA": TaggedValue((("DEFAULT", "ˈɑˌɑ"), ("NOUN", None))),
        "NoneTag": TaggedValue((("None", "n"),)),
        "empty": "",
        "variants": ("first", "second"),
        "word": WORD_ONLY,
    }
    lexicon = open_bytes(
        pack_typed(TypedLexiconData(entries), record_block_entries=2, key_block_entries=2)
    )
    try:
        assert dict(lexicon) == entries
        assert lexicon["live"] == {"DEFAULT": "lˈIv", "VERB": "lˈɪv"}
        assert lexicon.select("live", "VERB") == "lˈɪv"
        assert lexicon.select("AA", "NOUN") is None
        assert lexicon.select("AA", "MISSING") == "ˈɑˌɑ"
        assert lexicon.select("missing", missing="fallback") == "fallback"
        assert lexicon.get_record("live").kind == "tagged"
    finally:
        lexicon.close()


def test_source_adapters_preserve_shapes() -> None:
    source = parse_kokoro_json_bytes(b'{"live":{"DEFAULT":"l","VERB":"v"},"AA":{"NOUN":null}}')
    assert source.entries["live"] == TaggedValue((("DEFAULT", "l"), ("VERB", "v")))
    assert source.entries["AA"]["NOUN"] is None
    jsonl = parse_jsonl_bytes(
        b'{"word":"x","kind":"word"}\n{"word":"y","kind":"scalar","value":""}\n'
    )
    assert jsonl.entries == {"x": WORD_ONLY, "y": ""}
    tsv = parse_extended_tsv_bytes(b'a\ttagged\tDEFAULT\t"x"\na\ttagged\tNOUN\tnull\n')
    assert tsv.entries["a"]["NOUN"] is None
    assert parse_word_list_bytes("one\n二\n".encode()).entries["二"] is WORD_ONLY


def test_aliases_layers_and_comparison() -> None:
    raw = {"foo": "x", "Foo": "explicit", "bar": "b"}
    aliases = CaseAliasMapping(raw)
    assert aliases["Foo"] == "explicit"
    assert aliases["Bar"] == "b"
    assert len(aliases) == 4
    layered = LayeredLexicon(
        [
            LexiconLayer("gold", {"a": None, "b": "gold"}, {}),
            LexiconLayer("silver", {"a": "silver", "c": "silver"}, {}),
        ]
    )
    assert layered["a"] is None
    assert list(layered) == ["a", "b", "c"]
    result = compare({"a": "x"}, {"a": ("x",), "b": "y"})
    assert result.as_dict() == {
        "only_a": 0,
        "only_b": 1,
        "same": 0,
        "different": 1,
        "shape_different": 1,
    }


def test_layered_alias_iteration_is_unique() -> None:
    aliases = CaseAliasMapping({"apple": "a", "banana": "b"})
    layered = LayeredLexicon(
        [
            LexiconLayer("aliases", aliases, {}),
            LexiconLayer("other", {"Apple": "explicit", "blueberry": "bb"}, {}),
        ]
    )

    assert list(aliases) == ["apple", "banana", "Apple", "Banana"]
    assert list(layered) == ["apple", "banana", "Apple", "Banana", "blueberry"]
    assert len(layered) == len(set(layered)) == 5
    assert dict(layered) == {
        "apple": "a",
        "banana": "b",
        "Apple": "a",
        "Banana": "b",
        "blueberry": "bb",
    }


def test_layered_explicit_key_in_higher_layer_wins() -> None:
    layered = LayeredLexicon(
        [
            LexiconLayer("explicit", {"Apple": "explicit"}, {"rating": 4}),
            LexiconLayer("aliases", CaseAliasMapping({"apple": "alias"}), {"rating": 3}),
        ]
    )

    hit = layered.get_hit("Apple")
    assert hit is not None
    assert hit.value == "explicit"
    assert hit.name == "explicit"
    assert hit.index == 0
    assert hit.metadata == {"rating": 4}
    assert layered["Apple"] == "explicit"


def test_layered_hit_preserves_false_like_value() -> None:
    metadata = {"rating": 4}
    layered = LayeredLexicon(
        [
            LexiconLayer("first", {"x": None}, metadata),
            LexiconLayer("second", {"x": "fallback"}, {"rating": 3}),
        ]
    )

    hit = layered.get_hit("x")
    assert hit is not None
    assert hit.value is None
    assert hit.name == "first"
    assert hit.index == 0
    assert hit.metadata is metadata
    assert layered.get("x", "default") is None


def test_layered_close_is_idempotent_and_context_managed() -> None:
    class CloseOnceMapping(dict[str, str]):
        def __init__(self, *args: object, **kwargs: str) -> None:
            super().__init__(*args, **kwargs)
            self.close_count = 0

        def close(self) -> None:
            self.close_count += 1
            if self.close_count > 1:
                raise AssertionError("mapping closed more than once")

    mapping = CloseOnceMapping(x="value")
    layered = LayeredLexicon(
        [LexiconLayer("first", mapping, {}), LexiconLayer("duplicate", mapping, {})]
    )
    layered.close()
    layered.close()
    assert mapping.close_count == 1
    with pytest.raises(ValueError, match="closed"):
        layered.get("x")
    with pytest.raises(ValueError, match="closed"):
        list(layered)
    with pytest.raises(ValueError, match="closed"):
        len(layered)

    context_mapping = CloseOnceMapping(y="value")
    with LayeredLexicon([LexiconLayer("context", context_mapping, {})]) as context_layered:
        assert context_layered["y"] == "value"
    assert context_mapping.close_count == 1


def test_file_api_self_verification_and_export(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text(
        json.dumps({"a": "x", "live": {"DEFAULT": "l", "VERB": "v"}}), encoding="utf-8"
    )
    asset = tmp_path / "source.g2lex"
    pack_file(source, asset, input_format="kokoro-json")
    exported = tmp_path / "restored.jsonl"
    from g2lex import export_file, verify_file

    export_file(asset, exported, format="jsonl")
    assert verify_file(source, asset, input_format="kokoro-json")["lossless"]
    assert parse_jsonl_bytes(exported.read_bytes()).entries["live"]["VERB"] == "v"


_RESERVED_MANIFEST_KEYS = (
    "format",
    "schema",
    "entry_count",
    "value_model",
    "key_index",
    "record_codec",
    "record_block_entries",
    "key_block_entries",
    "source",
    "logical_sha256",
    "build",
)


@pytest.mark.parametrize("key", _RESERVED_MANIFEST_KEYS)
@pytest.mark.parametrize("metadata_source", ("explicit", "inherited"))
def test_reserved_manifest_metadata_is_rejected(key: str, metadata_source: str) -> None:
    if metadata_source == "explicit":
        data: TypedLexiconData | dict[str, object] = {"a": "x"}
        kwargs = {"metadata": {key: "collision"}}
    else:
        data = TypedLexiconData({"a": "x"}, metadata={key: "collision"})
        kwargs = {}

    with pytest.raises(ValueError, match=key):
        pack_typed(data, **kwargs)  # type: ignore[arg-type]


def test_custom_manifest_metadata_round_trips_deterministically() -> None:
    metadata = {"consumer": {"lexicon_id": "en-us:gold", "rating": 4}, "custom": "value"}
    first = pack_typed({"a": "x"}, metadata=metadata)
    second = pack_typed({"a": "x"}, metadata=metadata)
    assert first == second

    lexicon = open_bytes(first)
    try:
        assert lexicon.metadata["consumer"] == metadata["consumer"]
        assert lexicon.metadata["custom"] == "value"
    finally:
        lexicon.close()


def test_source_metadata_is_preserved_and_deterministic() -> None:
    source = SourceInfo(
        source_id="fixture",
        language="en",
        locale="en-US",
        provider="fixture-provider",
        revision="2026-01",
        pronunciation_alphabet="ipa",
        license_expression="CC0-1.0",
        parser_id="fixture-parser",
        parser_version="2",
    )
    data = TypedLexiconData({"word": "wɜːd"}, source=source)
    first = pack_typed(data)
    second = pack_typed(data)
    assert first == second
    lexicon = open_bytes(first)
    try:
        assert lexicon.metadata["source"]["pronunciation_alphabet"] == "ipa"
        assert lexicon.metadata["source"]["license_expression"] == "CC0-1.0"
        assert lexicon.metadata["source"]["parser_id"] == "fixture-parser"
        assert lexicon.metadata["source"]["source_sha256"] is None
    finally:
        lexicon.close()


def test_corrupt_g2lex_is_rejected() -> None:
    data = bytearray(pack_typed({"a": "x"}))
    data[0:4] = b"bad!"
    with pytest.raises(ValueError):
        open_bytes(data)
