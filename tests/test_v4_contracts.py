from pathlib import Path

from lexcompact import LexiconData, reduce_lexicon
from lexcompact.asset import load
from lexcompact.asset_v4 import dumps as dumps_v4
from lexcompact.asset_v4 import loads as loads_v4
from lexcompact.audit import audit_runtime_representation
from lexcompact.container import dumps as dump_container
from lexcompact.container import loads as load_container
from lexcompact.literals import BinaryPoolLiteralStore, RePairCodec, SymbolCodec
from lexcompact.membership import DafsaBinaryMembership, SortedUTF8Membership
from lexcompact.runtime import ReconstructionCandidate
from lexcompact.selectors import StaticPrioritySelector


def test_membership_backends_are_exact_and_roundtrip():
    words = ("Haus", "Haustür", "Tür", "你好")
    for backend in (
        DafsaBinaryMembership.from_words(words),
        SortedUTF8Membership.from_words(words),
    ):
        restored = type(backend).deserialize(backend.serialize())
        assert tuple(restored.iter_words()) == tuple(sorted(words))
        assert all(restored.contains(word) for word in words)
        assert not restored.contains("Hausx")
        assert restored.prefixes("Haustürx") == ("Haus", "Haustür")


def test_literal_pool_and_container_roundtrip():
    store = BinaryPoolLiteralStore({"A": ("x", "q"), "你好": ("ㄋㄧ3",)})
    restored = BinaryPoolLiteralStore.deserialize(store.serialize())
    assert restored["A"] == ("x", "q")
    container = load_container(dump_container({"a": b"one", "b": b"two"}))
    assert bytes(container["a"]) == b"one"


def test_v4_asset_and_audit_roundtrip(tmp_path: Path):
    source = LexiconData.from_pairs(("a", "x"), ("b", "y"), ("ab", "xy"))
    asset = reduce_lexicon(source).asset
    path = tmp_path / "candidate.lxc"
    path.write_bytes(dumps_v4(asset))
    restored = loads_v4(path.read_bytes())
    assert restored.lookup_all("ab") == ("xy",)
    assert audit_runtime_representation(restored)["per_generated_word_recipe_count"] == 0
    path.write_bytes(dumps_v4(asset))
    assert load(path).lookup_all("ab") == ("xy",)


def test_codecs_and_selector_are_deterministic():
    repair = RePairCodec()
    assert repair.decode(repair.encode(b"abcabcabc")) == b"abcabcabc"
    symbols = SymbolCodec("abˈ")
    assert symbols.decode(symbols.encode("aˈb")) == "aˈb"
    candidates = (
        ReconstructionCandidate("graphone", ("g",)),
        ReconstructionCandidate("compound", ("c",)),
    )
    assert StaticPrioritySelector().choose({}, candidates).stage_id == "compound"
