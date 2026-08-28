import json
from pathlib import Path

from g2lex import open as open_lexicon
from g2lex.asset import load
from g2lex.cli import main
from g2lex.io import read_lexicon


def test_json_cli_roundtrip(tmp_path: Path):
    source = tmp_path / "lexicon.json"
    source.write_text(json.dumps({"a": "x", "b": "y", "ab": "xy"}), encoding="utf-8")
    asset = tmp_path / "lexicon.g2lex"
    report = tmp_path / "report.json"
    assert main(["pack", str(source), str(asset), "--report", str(report)]) == 0
    assert main(["verify", str(source), str(asset)]) == 0
    loaded = open_lexicon(asset)
    try:
        assert len(loaded) == 3
        assert loaded.get("ab") == "xy"
    finally:
        loaded.close()
    restored = tmp_path / "restored.json"
    assert main(["restore", str(asset), str(restored), "--format", "json"]) == 0
    assert read_lexicon(restored).entries == read_lexicon(source).entries
    assert json.loads(report.read_text())["self_verified"]


def test_tsv_duplicate_variants(tmp_path: Path):
    source = tmp_path / "lexicon.tsv"
    source.write_text("A\tx\nA\tq\nB\ty\nAB\txy\nAB\tqy\n", encoding="utf-8")
    asset = tmp_path / "lexicon.lxc"
    assert main(["reduce", str(source), str(asset), "--format", "tsv"]) == 0
    assert main(["experimental", "verify-reduced", str(source), str(asset), "--format", "tsv"]) == 0
    assert load(asset).lookup_all("AB") == ("xy", "qy")
