from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from g2lex.asset import dumps, load, load_traversable, loads
from g2lex.asset_v4 import dumps as dumps_v4
from g2lex.asset_v4 import loads as loads_v4
from g2lex.builder import build_implicit_lexicon
from g2lex.container import dumps as container_dumps
from g2lex.literals import BinaryPoolLiteralStore
from g2lex.membership import BloomMembership, DafsaBinaryMembership
from g2lex.model import LexiconData
from g2lex.runtime import RuntimeProgram
from g2lex.selectors import StaticPrioritySelector


def _asset():
    source = LexiconData.from_pairs(("a", "x"), ("b", "y"), ("ab", "xy"))
    return build_implicit_lexicon(source).asset


def _rewrite_zip(raw: bytes, mutate) -> bytes:
    source = io.BytesIO(raw)
    output = io.BytesIO()
    with zipfile.ZipFile(source) as archive, zipfile.ZipFile(output, "w") as result:
        for name in archive.namelist():
            value = archive.read(name)
            if name == "manifest.json":
                value = mutate(value)
            result.writestr(name, value)
    return output.getvalue()


def test_v3_roundtrip_paths_determinism_and_missing_members(tmp_path: Path) -> None:
    asset = _asset()
    raw = dumps(asset)
    assert raw == dumps(asset)
    restored = loads(raw)
    assert restored.lookup_all("ab") == ("xy",)
    path = tmp_path / "asset.lxc"
    path.write_bytes(raw)
    assert load(path).lookup_all("a") == ("x",)

    class Resource:
        def read_bytes(self) -> bytes:
            return raw

    assert load_traversable(Resource()).lookup_all("b") == ("y",)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
    for missing in names:
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(raw)) as source, zipfile.ZipFile(output, "w") as target:
            for name in source.namelist():
                if name != missing:
                    target.writestr(name, source.read(name))
        with pytest.raises(ValueError, match="missing"):
            loads(output.getvalue())

    invalid = _rewrite_zip(raw, lambda _value: b"{}")
    with pytest.raises(ValueError, match="unsupported"):
        loads(invalid)
    wrong_count = _rewrite_zip(
        raw,
        lambda value: json.dumps(
            {**json.loads(value), "literal_word_count": 999}, separators=(",", ":")
        ).encode(),
    )
    with pytest.raises(ValueError, match="literal count"):
        loads(wrong_count)


def test_asset_dispatches_v1_and_v4() -> None:
    raw_v1 = __import__("g2lex.format", fromlist=["pack_typed"]).pack_typed({"a": "x"})
    assert loads(raw_v1)["a"] == "x"
    asset = _asset()
    raw_v4 = dumps_v4(asset)
    assert loads(raw_v4).lookup_all("ab") == ("xy",)


def test_v4_backend_roundtrips_and_runtime_program() -> None:
    asset = _asset()
    asset.literals = BinaryPoolLiteralStore(asset.literals)
    exact = DafsaBinaryMembership.from_words(tuple(asset.membership.iter_words()))
    asset.membership = BloomMembership(exact, bits_per_key=8, hash_count=2)
    asset.runtime_program = RuntimeProgram.from_v4(
        asset.composer, StaticPrioritySelector(), stage_ids=("compound",)
    )
    raw = dumps_v4(asset)
    restored = loads_v4(raw)
    assert restored.lookup_all("ab") == ("xy",)
    assert restored.literals.backend_id == "binary-pool-v2"
    assert restored.membership.backend_id.startswith("bloom")
    assert restored.runtime_program is not None

    sections = __import__("g2lex.asset_v4", fromlist=["asset_sections"]).asset_sections(asset)
    sections.pop("membership.bloom-exact")
    with pytest.raises(ValueError, match="missing its exact"):
        loads_v4(container_dumps(sections))
    sections = __import__("g2lex.asset_v4", fromlist=["asset_sections"]).asset_sections(asset)
    sections.pop("literal-index.json")
    with pytest.raises(ValueError, match="missing section"):
        loads_v4(container_dumps(sections))
