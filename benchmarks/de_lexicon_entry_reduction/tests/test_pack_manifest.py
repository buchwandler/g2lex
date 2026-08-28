from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from benchmarks.de_lexicon_entry_reduction.sources import ROOT, load_manifest


def test_codecrate_includes_tsv_and_local_sources_exist():
    document = tomllib.loads(Path(".codecrate.toml").read_text(encoding="utf-8"))
    assert "**/*.tsv" in document["codecrate"]["include"]
    for spec in load_manifest().values():
        if spec.kind == "local_file":
            assert spec.filename is not None
            assert (ROOT / spec.filename).is_file()
