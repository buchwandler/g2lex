from pathlib import Path

from lexcompact import LexiconData, ReductionConfig, SegmentationScorer, reduce_lexicon
from lexcompact.asset import dumps, load, loads, save
from lexcompact.profiles.german import german_rules
from lexcompact.verify import verify_candidate


def test_generic_exact_concat_and_oov_gate():
    source = LexiconData.from_pairs(("a", "x"), ("b", "y"), ("ab", "xy"))
    result = reduce_lexicon(source)
    assert result.metrics.literal_word_count == 2
    assert result.metrics.generated_word_count == 1
    asset = loads(dumps(result.asset))
    assert asset.lookup_all("ab") == ("xy",)
    assert asset.lookup("abab") is None
    assert "abab" not in asset
    assert verify_candidate(asset, source)["lossless"]


def test_generic_does_not_apply_german_stress_rule():
    source = LexiconData.from_pairs(("Haus", "hˈaʊs"), ("tür", "tˈyːɐ"), ("Haustür", "hˈaʊstˌyːɐ"))
    generic = reduce_lexicon(source)
    german = reduce_lexicon(source, rules=german_rules())
    assert "Haustür" in generic.asset.literals
    assert "Haustür" not in german.asset.literals


def test_unicode_languages_are_opaque():
    source = LexiconData.from_pairs(
        ("你", "ㄋㄧ3"),
        ("好", "ㄏㄠ3"),
        ("你好", "ㄋㄧ3ㄏㄠ3"),
        ("ش", "ʃ"),
        ("مس", "ms"),
        ("شمس", "ʃms"),
    )
    asset = loads(dumps(reduce_lexicon(source).asset))
    assert asset.lookup("你好") == "ㄋㄧ3ㄏㄠ3"
    assert asset.lookup("شمس") == "ʃms"


def test_ordered_variants_are_exact():
    source = LexiconData.from_pairs(("A", "x"), ("A", "q"), ("B", "y"), ("AB", "xy"), ("AB", "qy"))
    asset = loads(dumps(reduce_lexicon(source).asset))
    assert asset.lookup_all("AB") == ("xy", "qy")


def test_search_limit_is_conservative():
    source = LexiconData.from_pairs(("a", "x"), ("aa", "xx"), ("aaaa", "xxxx"))
    result = reduce_lexicon(source, config=ReductionConfig(max_states=1))
    assert verify_candidate(result.asset, source)["lossless"]
    assert result.search_limit_words >= 1


def test_single_file_serialization_is_deterministic(tmp_path: Path):
    source = LexiconData.from_pairs(("a", "x"), ("b", "y"), ("ab", "xy"))
    result = reduce_lexicon(source)
    assert dumps(result.asset) == dumps(result.asset)
    path = tmp_path / "x.lxc"
    save(path, result.asset)
    assert load(path).lookup("ab") == "xy"


def test_recursive_generated_constituents_survive_single_file_roundtrip():
    source = LexiconData.from_pairs(
        ("A", "a"), ("B", "b"), ("C", "c"), ("AB", "ab"), ("ABC", "abc")
    )
    config = ReductionConfig(
        max_components=2,
        recursive_components=True,
        max_recursive_depth=4,
        segmentation_scorer=SegmentationScorer(),
    )
    result = reduce_lexicon(source, config=config)
    assert result.metrics.literal_word_count == 3
    assert result.metrics.generated_word_count == 2
    asset = loads(dumps(result.asset))
    assert asset.composer.recursive_components
    assert asset.composer.segmentation_scorer is not None
    assert asset.lookup_all("ABC") == ("abc",)
    assert verify_candidate(asset, source)["lossless"]
