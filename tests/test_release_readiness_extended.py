from __future__ import annotations

import json
from pathlib import Path

import pytest

from g2lex import WORD_ONLY, TaggedValue
from g2lex.adapters.json_map import parse_json_map_bytes
from g2lex.adapters.pls import parse_pls_bytes
from g2lex.adapters.tsv import parse_extended_tsv_bytes, parse_tsv_bytes
from g2lex.backends import (
    build_codec,
    build_literal_store,
    build_membership_backend,
    supported_backend_names,
)
from g2lex.format import pack_typed
from g2lex.g2p import CARTModel, CARTReconstructor, train_cart
from g2lex.graphone import GraphoneModel, GraphoneReconstructor, train_graphone
from g2lex.io import LexiconFormatError, parse_json_bytes
from g2lex.io import parse_tsv_bytes as parse_plain_tsv
from g2lex.layers import CaseAliasMapping, LayeredLexicon, LexiconLayer
from g2lex.neural import NeuralModel, NeuralReconstructor, train_neural
from g2lex.operations import convert_file, export_file, inspect_file, pack_file, verify_file
from g2lex.reconstructors import (
    AffixRule,
    MorphologyReconstructor,
    RewriteReconstructor,
    RewriteRule,
    induce_rewrite_rules,
    mine_morphology,
)
from g2lex.runtime import ReconstructionCandidate
from g2lex.selectors import (
    GradientBoostedTreeSelector,
    HashedLogisticSelector,
    RandomForestSelector,
    StaticPrioritySelector,
    TreePredicate,
    TreeSelector,
    train_hashed_logistic,
)
from g2lex.training.alignment import align
from g2lex.value import as_plain_selector, as_plain_value, canonical_bytes, validate_selector_value


def test_json_map_and_tsv_error_paths_and_shapes() -> None:
    source = parse_json_map_bytes(b'{"word":"w", "variants":["a", "b"], "tagged":{"noun":null}}')
    assert source.entries["tagged"] == TaggedValue((("noun", None),))
    with pytest.raises(ValueError, match="invalid UTF-8 JSON"):
        parse_json_map_bytes(b"{")
    with pytest.raises(TypeError, match="root"):
        parse_json_map_bytes(b"[]")
    with pytest.raises(ValueError, match="keys"):
        parse_json_map_bytes(b'{"": "x"}')
    with pytest.raises(ValueError, match="disabled"):
        parse_json_map_bytes(b'{"x": {"tag": "v"}}', allow_tagged=False)
    with pytest.raises(ValueError, match="expected string"):
        parse_json_map_bytes(b'{"x": 4}')

    assert parse_tsv_bytes(b"a\tx\na\ty\n").entries == {"a": ("x", "y")}
    assert parse_extended_tsv_bytes(
        b'word\tword\t\t\nscalar\tscalar\t\t"x"\nlist\tlist\t\t["a","b"]\n'
    ).entries == {"word": WORD_ONLY, "scalar": "x", "list": ("a", "b")}
    with pytest.raises(ValueError, match="unsupported kind"):
        parse_extended_tsv_bytes(b"x\tbad\t\t\n")
    with pytest.raises(ValueError, match="tagged row"):
        parse_extended_tsv_bytes(b'x\ttagged\t\t"v"\n')
    with pytest.raises(ValueError, match="invalid value JSON"):
        parse_extended_tsv_bytes(b"x\tscalar\t\t{\n")
    with pytest.raises(ValueError, match="empty spelling"):
        parse_tsv_bytes(b"\tx\n")


def test_plain_io_and_pls_edge_cases(tmp_path: Path) -> None:
    assert parse_json_bytes(b'{"a":"x", "b":["y", "z"]}').lookup("b") == "y"
    with pytest.raises(LexiconFormatError, match="root"):
        parse_json_bytes(b"[]")
    with pytest.raises(LexiconFormatError, match="value"):
        parse_json_bytes(b'{"x": []}')
    with pytest.raises(LexiconFormatError, match="fields"):
        parse_plain_tsv(b"x\ty\textra\n")
    with pytest.raises(ValueError, match="unsupported"):
        parse_pls_bytes(
            b'<lexicon alphabet="ipa"><lexeme><grapheme>x</grapheme><example>y</example></lexeme></lexicon>'
        )
    with pytest.raises(ValueError, match="default alphabet"):
        parse_pls_bytes(b"<lexicon/>")
    path = tmp_path / "source.json"
    path.write_text('{"a":"x"}', encoding="utf-8")
    assert parse_json_bytes(path.read_bytes(), path=path).source.path == str(path)


def test_operations_export_convert_inspect_and_verify(tmp_path: Path) -> None:
    source = tmp_path / "source.lxc.tsv"
    source.write_text(
        'word\tword\t\t\nscalar\tscalar\t\t"x"\ntag\ttagged\tnoun\t"n"\n',
        encoding="utf-8",
    )
    asset = tmp_path / "asset.g2lex"
    pack_file(source, asset, input_format="lxc-tsv")
    assert verify_file(source, asset, input_format="lxc-tsv")["lossless"]
    info = inspect_file(asset)
    assert info["format"] == "g2lex.lexicon.v1"
    for fmt, suffix in (("jsonl", ".jsonl"), ("lxc-tsv", ".tsv")):
        output = tmp_path / f"export{suffix}"
        export_file(asset, output, format=fmt)
        assert output.exists()
    plain_source = tmp_path / "plain-source.tsv"
    plain_source.write_text("a\tx\n", encoding="utf-8")
    plain_asset = tmp_path / "plain.g2lex"
    pack_file(plain_source, plain_asset, input_format="tsv")
    export_file(plain_asset, tmp_path / "export.json", format="json-map")
    words = tmp_path / "words.txt"
    with pytest.raises(ValueError, match="membership-only"):
        export_file(asset, words, format="words")
    convert_file(
        plain_source, tmp_path / "converted.json", input_format="tsv", output_format="json"
    )
    with pytest.raises(ValueError, match="unsupported export"):
        export_file(asset, tmp_path / "bad", format="bad")
    with pytest.raises(ValueError, match="unsupported conversion"):
        convert_file(source, tmp_path / "bad", input_format="lxc-tsv", output_format="bad")
    plain = tmp_path / "plain.tsv"
    plain.write_text("a\tx\na\ty\n", encoding="utf-8")
    convert_file(plain, tmp_path / "plain.jsonl", input_format="tsv", output_format="jsonl")


def test_backends_and_values() -> None:
    names = supported_backend_names()
    assert "sorted-utf8" in names["membership"]
    words = ("a", "ab", "b")
    for name in names["membership"]:
        backend = build_membership_backend(name, words)
        assert all(backend.contains(word) for word in words)
        assert not backend.contains("missing")
    for name in names["literal"]:
        store = build_literal_store(name, {"a": ("x",)})
        assert store["a"] == ("x",)
    assert build_codec("utf8") is None
    repair = build_codec("repair")
    assert repair.decode(repair.encode(b"abcabc")) == b"abcabc"
    for name in ("symbol-u8", "token-spaced"):
        codec = build_codec(name, ("a", "b"))
        assert codec.decode(codec.encode("a")) == "a"
    token_codec = build_codec("token-spaced", ("a", "b"))
    assert token_codec.decode_tokens(token_codec.encode_tokens(("a", "b"))) == ("a", "b")
    with pytest.raises(ValueError, match="unknown"):
        build_membership_backend("bad", words)
    with pytest.raises(ValueError, match="unknown"):
        build_literal_store("bad", {})
    with pytest.raises(ValueError, match="unknown"):
        build_codec("bad")
    assert as_plain_value(WORD_ONLY) is WORD_ONLY
    tagged = TaggedValue((("a", ("x", "y")),))
    assert as_plain_value(tagged) == {"a": ["x", "y"]}
    assert as_plain_selector(("x", "y")) == ["x", "y"]
    with pytest.raises(TypeError):
        validate_selector_value(["x"])
    assert canonical_bytes({"a": "x"})


def test_version_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    import g2lex._version as version

    monkeypatch.setenv("G2LEX_VERSION", "9.9.9")
    assert version.get_version() == "9.9.9"
    monkeypatch.delenv("G2LEX_VERSION")
    monkeypatch.setattr(version.subprocess, "check_output", lambda *a, **k: "v1.2.3-0-gabc")
    assert version.get_version() == "1.2.3"
    monkeypatch.setattr(version.subprocess, "check_output", lambda *a, **k: "v1.2.3-2-gabc")
    assert version.get_version() == "1.2.3.post2+gabc"
    monkeypatch.setattr(version.subprocess, "check_output", lambda *a, **k: "v1.2.3-0-gabc-dirty")
    assert version.get_version() == "1.2.3.dev0+gabc.dirty"
    monkeypatch.setattr(version.subprocess, "check_output", lambda *a, **k: "not-a-tag")
    assert version.get_version() == "0.1.0"

    def fail(*args, **kwargs):
        raise OSError

    monkeypatch.setattr(version.subprocess, "check_output", fail)
    assert version.get_version() == "0.1.0"


def test_version_resolution_from_sdist_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import g2lex._version as version

    (tmp_path / "PKG-INFO").write_text(
        "Metadata-Version: 2.4\nName: g2lex\nVersion: 1.2.3\n",
        encoding="utf-8",
    )
    assert version._sdist_version(tmp_path) == "1.2.3"

    monkeypatch.setattr(version, "_sdist_version", lambda root: "1.2.3")

    def fail(*args, **kwargs):
        raise OSError

    monkeypatch.setattr(version.subprocess, "check_output", fail)
    assert version.get_version() == "1.2.3"



def test_training_models_and_alignment() -> None:
    assert align("ab", "xy", max_output_chunk_length=1) == (("a", "x"), ("b", "y"))
    with pytest.raises(ValueError, match="non-negative"):
        align("a", "x", max_output_chunk_length=-1)
    with pytest.raises(ValueError, match="cannot be aligned"):
        align("ab", "x", max_output_chunk_length=0)

    cart = train_cart([("ab", "xy"), ("a", "x")])
    assert cart.predict("ab")
    assert CARTModel.deserialize(cart.serialize()).as_dict() == cart.as_dict()
    assert CARTReconstructor(cart).candidates("ab")[0].analysis_kind == "cart"
    with pytest.raises(ValueError, match="budget"):
        train_cart([("a", "x")], max_bytes=1)

    graphone = train_graphone([("ab", "xy"), ("a", "x")])
    assert graphone.predict("ab")
    assert GraphoneModel.deserialize(graphone.serialize()).as_dict() == graphone.as_dict()
    assert GraphoneReconstructor(graphone).candidates("ab")
    assert not GraphoneReconstructor(graphone).candidates("?")
    with pytest.raises(ValueError, match="order"):
        GraphoneModel((), order=5)

    neural = train_neural([("ab", "xy"), ("a", "z"), ("long", "x")])
    assert neural.predict("ab") == "xy"
    assert NeuralModel.deserialize(neural.serialize()).as_dict() == neural.as_dict()
    assert NeuralReconstructor(neural).candidates("ab")[0].analysis_kind == "lstm"
    with pytest.raises(ValueError, match="architecture"):
        NeuralModel("bad", ())
    assert train_neural([("ab", "xy")]).predict("ab") == "xy"


def test_selectors_choose_and_serialize() -> None:
    candidates = (
        ReconstructionCandidate("cart", ("c",), "2", score=2),
        ReconstructionCandidate("graphone", ("g",), "1", score=1),
    )
    assert StaticPrioritySelector().choose({}, candidates).stage_id == "cart"
    tree = TreeSelector((TreePredicate("kind", "yes", "graphone"),))
    assert tree.choose({"kind": "yes"}, candidates).stage_id == "graphone"
    assert tree.choose({"kind": "no"}, candidates).stage_id == "cart"
    logistic = train_hashed_logistic([{"features": {"kind": "yes"}, "target_stage": "graphone"}])
    assert logistic.choose({"kind": "yes"}, candidates)
    assert HashedLogisticSelector().choose({}, ()) is None
    forest = RandomForestSelector((tree, tree))
    assert forest.choose({"kind": "yes"}, candidates).stage_id == "graphone"
    assert RandomForestSelector(()).choose({}, candidates) is None
    gbdt = GradientBoostedTreeSelector((("graphone", 3),))
    assert gbdt.choose({}, candidates).stage_id == "graphone"
    assert gbdt.choose({}, ()) is None
    assert tree.serialized_bytes > 0
    with pytest.raises(ValueError, match="budget"):
        train_hashed_logistic([{"features": {"x": "y"}, "target_stage": "cart"}], max_bytes=1)


def test_reconstructors_and_layered_mappings() -> None:
    context = {"stem": ("s",)}
    rule = AffixRule(1, spelling_suffix="s", strip_suffix="s", pronunciation_suffix_add="z")
    assert rule.apply("stems", context)[0].pronunciation == ("sz",)
    assert not rule.apply("stem", context)
    assert rule._transform("abc") == "abcz"
    morph = MorphologyReconstructor([rule])
    assert morph.candidates("stems", context)
    assert mine_morphology({"a": ("x",), "as": ("xz",)}, min_support=1)

    rewrite = RewriteRule(1, "replace", pattern="x", replacement="y")
    candidate = ReconstructionCandidate("cart", ("x",))
    assert rewrite.apply("word", "x") == "y"
    assert RewriteReconstructor([rewrite]).candidates("word", {"candidates": (candidate,)})
    assert induce_rewrite_rules([{"pattern": "x", "operation": "delete"}])[0].apply("w", "x") == ""
    with pytest.raises(ValueError, match="unknown"):
        RewriteRule(1, "bad", pattern="x").apply("w", "x")

    raw = {"word": "x"}
    aliases = CaseAliasMapping(raw)
    assert aliases.get("Missing", "fallback") == "fallback"
    assert "Word" in aliases and len(aliases) == 2
    layered = LayeredLexicon(
        [LexiconLayer("a", {"x": None}, {}), LexiconLayer("b", {"x": "y", "z": "z"}, {})]
    )
    assert layered["x"] is None
    assert list(layered) == ["x", "z"]
    assert layered.get("missing", "default") == "default"
    with pytest.raises(KeyError):
        layered["missing"]


def test_kokoro_cache_and_diagnostics_artifacts(tmp_path: Path) -> None:
    from g2lex.diagnostics import _boundary_family, write_diagnostics
    from g2lex.kokoro import (
        clear_lexicon_cache,
        layer_kokoro_lexica,
        lexicon_cache_info,
        open_kokoro_lexicon,
    )

    assert _boundary_family("ax", "ay", ("a", "x"), (("a",), ("x",)), 2)["local"]
    assert (
        _boundary_family("aˈb", "aˌb", ("a", "b"), (("a",), ("b",)), 1)["family"]
        == "primary stress → secondary stress"
    )
    result = {
        "failure_family_summary": {},
        "alternate_rule_summary": {},
        "linker_summary": {},
        "top_k_segmentation_summary": {},
        "boundary_patterns": [],
        "failure_details": [],
    }
    write_diagnostics(tmp_path, result)
    assert (tmp_path / "failure_families.tsv").exists()

    path = tmp_path / "word.g2lex"
    path.write_bytes(pack_typed({"word": "w"}))
    clear_lexicon_cache()
    first = open_kokoro_lexicon(path, cache_key="x")
    second = open_kokoro_lexicon(path, cache_key="x")
    assert second is not first
    assert first["word"] == "w"
    assert second["word"] == "w"
    assert lexicon_cache_info().hits == 0
    assert lexicon_cache_info().misses == 2
    first.close()
    assert second["word"] == "w"
    second.close()
    layered = layer_kokoro_lexica({"word": "gold"}, {"other": "silver"}, aliases=True)
    assert layered["word"] == "gold"


def test_io_writers_and_format_dispatch(tmp_path: Path) -> None:
    from g2lex.adapters.words import parse_word_list_bytes
    from g2lex.io import parse_typed_bytes, read_typed_lexicon, write_lexicon
    from g2lex.model import LexiconData

    data = LexiconData.from_pairs(("a", "x"), ("a", "y"))
    write_lexicon(tmp_path / "out.json", data)
    write_lexicon(tmp_path / "out.tsv", data)
    assert read_typed_lexicon(tmp_path / "out.json", format="json").entries["a"] == ("x", "y")
    assert read_typed_lexicon(tmp_path / "out.tsv", format="tsv").entries["a"] == ("x", "y")
    assert parse_typed_bytes(b"a\tx\n", format="tsv").entries["a"] == ("x",)
    assert parse_typed_bytes(b"a\n", format="words").entries["a"] is WORD_ONLY
    with pytest.raises(ValueError, match="unsupported"):
        parse_typed_bytes(b"", format="bad")
    with pytest.raises(ValueError, match="unsupported"):
        write_lexicon(tmp_path / "out.bad", data, format="bad")
    with pytest.raises(ValueError, match="empty word"):
        parse_word_list_bytes(b"a\n\n")


def test_exact_verification_mismatch_reports() -> None:
    from g2lex.model import LexiconData
    from g2lex.verify import adversarial_misses, verify_candidate
    from g2lex.verify_exact import verify_typed

    baseline = LexiconData.from_pairs(("a", "x"), ("a", "y"), ("b", "z"))
    assert adversarial_misses(("ab", "c"), limit=2)
    result = verify_typed({"a": ("y", "x")}, {"a": ("x", "y"), "b": "z"})
    assert result["variant_order_mismatch"] == 1
    assert result["missing"] == 1
    from g2lex.reduce import reduce_lexicon

    candidate = reduce_lexicon(LexiconData.from_pairs(("a", "wrong"))).asset
    checked = verify_candidate(candidate, baseline, miss_words=("other",))
    assert not checked["lossless"]
    assert checked["missing_words"] == 1
    assert checked["pronunciation_mismatches"] == 1


def test_v4_selector_decoding_and_asset_errors() -> None:
    from g2lex.asset_v4 import _selector_from_dict

    assert _selector_from_dict(None).selector_id == "static-priority"
    assert (
        _selector_from_dict({"selector_id": "tree", "predicates": [["x", "y", "cart"]]}).selector_id
        == "tree"
    )
    assert (
        _selector_from_dict(
            {"selector_id": "hashed-logistic", "weights": [[1, [["cart", 2]]]]}
        ).selector_id
        == "hashed-logistic"
    )
    assert (
        _selector_from_dict({"selector_id": "gbdt", "stage_scores": [["cart", 1]]}).selector_id
        == "gbdt"
    )
    with pytest.raises(ValueError, match="unsupported serialized"):
        _selector_from_dict({"selector_id": "bad"})
    from g2lex.asset_v4 import loads

    with pytest.raises(ValueError, match="truncated"):
        loads(b"not-an-asset")


def test_reconstructor_conditions_and_runtime_helpers() -> None:
    from g2lex.reconstructors import _capitalization
    from g2lex.runtime import OverlayMapping, RuntimeProgram

    assert _capitalization("ABC") == "upper"
    assert _capitalization("Abc") == "initial-upper"
    assert _capitalization("abc") == "lower"
    assert _capitalization("aB") == "mixed"
    rule = AffixRule(
        2,
        spelling_prefix="re",
        strip_prefix="re",
        min_stem_length=2,
        required_left_context="st",
        required_right_context="m",
        capitalization_class="lower",
        pronunciation_prefix_remove="s",
        pronunciation_suffix_remove="m",
        pronunciation_prefix_add="r",
        pronunciation_suffix_add="!",
    )
    assert not rule.apply("reabc", {"abc": ("abc",)})
    assert rule.apply("restm", {"stm": ("sm",)})[0].pronunciation == ("r!",)
    assert AffixRule(3).apply("word", object()) == ()
    assert RewriteRule(1, "insert", pattern="x", replacement="y").apply("w", "x") == "xy"
    assert RewriteRule(1, "delete", pattern="x").apply("w", "x") == ""
    assert RewriteRule(1, "replace", pattern="x", replacement="y").apply("w", "x") == "y"
    assert RewriteRule(1, "replace", spelling_left="q", pattern="x").apply("w", "x") is None
    overlay = OverlayMapping({"a": ("x",), "b": ("y",)}, {"a": ("z",), "c": ("q",)})
    assert overlay["a"] == ("z",) and overlay["b"] == ("y",)
    assert list(overlay) == ["a", "c", "b"]
    assert len(overlay) == 3 and "c" in overlay
    assert overlay.get("missing", "fallback") == "fallback"
    assert RuntimeProgram().as_dict()["version"] == "1"


def test_diagnostics_analysis_and_writers(tmp_path: Path) -> None:
    from g2lex.diagnostics import analyze_failures, write_diagnostics
    from g2lex.model import LexiconData
    from g2lex.reduce import reduce_lexicon

    source = LexiconData.from_pairs(("a", "x"), ("b", "y"), ("ab", "xy"))
    asset = reduce_lexicon(source).asset
    result = analyze_failures(
        source,
        asset,
        failures=[
            {
                "word": "a",
                "reason": "pronunciation-mismatch",
                "candidate": ["bad"],
                "candidate_rule": "missing",
            }
        ],
    )
    assert result["pronunciation_mismatch_count"] == 1
    result["boundary_patterns"] = [
        {
            "support_count": 1,
            "exact_count_if_applied": 0,
            "conflict_count": 0,
            "word_count": 1,
            "component_count": 2,
            "spelling_left_context": "a",
            "spelling_right_context": "b",
            "phoneme_left_context": "x",
            "phoneme_right_context": "y",
            "edit_template": "replace",
        }
    ]
    result["failure_details"] = [
        {
            "word": "ab",
            "selected_rule": "missing",
            "selected_segmentation": ["a", "b"],
            "candidate_pronunciation": ["bad"],
            "expected_pronunciation": ["xy"],
            "top_k_exact_rank": None,
        }
    ]
    write_diagnostics(tmp_path, result)
    assert (tmp_path / "top_100_boundary_patterns.tsv").read_text().startswith("support_count")
    assert (tmp_path / "failure_families.tsv").read_text().count("ab") == 1


def test_reduction_asset_branding_and_legacy_readers() -> None:
    import io
    import zipfile

    from g2lex.asset import ASSET_FORMAT as V3_FORMAT
    from g2lex.asset import dumps as dumps_v3
    from g2lex.asset import loads as loads_v3
    from g2lex.asset_v4 import ASSET_FORMAT as V4_FORMAT
    from g2lex.asset_v4 import asset_sections
    from g2lex.asset_v4 import dumps as dumps_v4
    from g2lex.asset_v4 import loads as loads_v4
    from g2lex.container import dumps as dump_container
    from g2lex.model import LexiconData
    from g2lex.reduce import reduce_lexicon

    source = LexiconData.from_pairs(("a", "x"), ("b", "y"), ("ab", "xy"))
    asset = reduce_lexicon(source).asset
    assert V3_FORMAT == "g2lex.asset.v3"
    data_v3 = dumps_v3(asset)
    with zipfile.ZipFile(io.BytesIO(data_v3), "r") as archive:
        manifest = json.loads(archive.read("manifest.json"))
        members = {name: archive.read(name) for name in archive.namelist()}
    assert manifest["format"] == V3_FORMAT
    manifest["format"] = "lexcompact.asset.v3"
    members["manifest.json"] = (
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    )
    legacy_buffer = io.BytesIO()
    with zipfile.ZipFile(legacy_buffer, "w") as archive:
        for name, value in members.items():
            archive.writestr(name, value)
    assert loads_v3(legacy_buffer.getvalue()).lookup("ab") == "xy"
    assert V4_FORMAT == "g2lex.asset.v4"
    data_v4 = dumps_v4(asset)
    sections = asset_sections(asset)
    manifest = json.loads(sections["manifest.json"])
    assert manifest["format"] == V4_FORMAT
    manifest["format"] = "lexcompact.asset.v4"
    sections["manifest.json"] = (
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    )
    legacy_v4 = dump_container(sections)
    assert loads_v4(legacy_v4).lookup("ab") == "xy"
    assert loads_v4(data_v4).lookup("ab") == "xy"


def test_cli_user_facing_operations(tmp_path: Path) -> None:
    from g2lex.cli import main

    source = tmp_path / "source.tsv"
    source.write_text("a\tx\nb\ty\n", encoding="utf-8")
    asset = tmp_path / "source.g2lex"
    assert main(["pack", str(source), str(asset), "--format", "tsv"]) == 0
    assert main(["lookup", str(asset), "a"]) == 0
    assert main(["lookup", str(asset), "missing"]) == 1
    assert main(["inspect", str(asset)]) == 0
    assert main(["export", str(asset), str(tmp_path / "out.jsonl"), "--format", "jsonl"]) == 0
    assert (
        main(
            [
                "convert",
                str(source),
                str(tmp_path / "out.json"),
                "--input-format",
                "tsv",
                "--format",
                "json",
            ]
        )
        == 0
    )
    assert main(["diff", str(asset), str(asset)]) == 0
