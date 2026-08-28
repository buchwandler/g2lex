from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.de_lexicon_entry_reduction.aggregate_results import aggregate
from benchmarks.de_lexicon_entry_reduction.config import load_config
from benchmarks.de_lexicon_entry_reduction.download import source_url
from benchmarks.de_lexicon_entry_reduction.run_config import run_config
from benchmarks.de_lexicon_entry_reduction.sources import (
    load_manifest,
    load_source,
    resolve_source_path,
)

FIXTURE = Path(__file__).parents[1] / "fixtures" / "toy.tsv"
CONFIG = Path(__file__).parents[1] / "configs" / "crane-wiktionary-v4-benchmark.toml"
REVISION = "bfd51698069a30e1b20bbf54479b55af50b4161d"
SHA256 = "04a3909f07cd08615157393814188b420a7c3c5035cf7a0608d31be07892be29"


def test_crane_wiktionary_pin() -> None:
    spec = load_manifest()["crane_wiktionary"]
    assert spec.kind == "huggingface_file"
    assert spec.values["repo_type"] == "dataset"
    assert spec.values["repo_id"] == "crane-local-ai/g2p-lexicons"
    assert spec.revision == REVISION
    assert spec.filename == "de/de.tsv"
    assert spec.values["sha256"] == SHA256
    assert spec.values["size_bytes"] == 32367922
    assert spec.values["license"] == "CC-BY-SA-4.0"


def test_crane_download_url_is_dataset_revision_pinned() -> None:
    spec = load_manifest()["crane_wiktionary"]
    url = source_url(spec)
    assert "/datasets/crane-local-ai/g2p-lexicons/" in url
    assert REVISION in url
    assert url.endswith("/de/de.tsv")


def test_crane_default_cache_discovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from benchmarks.de_lexicon_entry_reduction import sources

    spec = load_manifest()["crane_wiktionary"]
    expected = tmp_path / "crane_wiktionary" / REVISION / "de" / "de.tsv"
    expected.parent.mkdir(parents=True)
    expected.write_text("Haus\thaus\n", encoding="utf-8")
    monkeypatch.setattr(sources, "DEFAULT_CACHE_DIR", tmp_path)
    assert resolve_source_path(spec) == expected


def test_missing_crane_source_explains_explicit_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from benchmarks.de_lexicon_entry_reduction import sources

    monkeypatch.setattr(sources, "DEFAULT_CACHE_DIR", tmp_path)
    with pytest.raises(FileNotFoundError, match=r"--source crane_wiktionary --download"):
        load_source("crane_wiktionary")


def test_tsv_runtime_view_preserves_shape_and_variant_order(tmp_path: Path) -> None:
    path = tmp_path / "variants.tsv"
    path.write_text(
        "Haus\thˈaʊs\n"
        "Haus\thaʊs\n"
        "Haus\thaʊs\n"
        "Tür\ttˈyːɐ\n"
        "Haustür\thˈaʊstˌyːɐ\n",
        encoding="utf-8",
    )
    source = load_source("crane_wiktionary", path=path)
    assert source.physical_rows == 5
    assert len(source.entries) == 3
    assert source.variant_count == 4
    assert source.physical_rows - source.variant_count == 1
    assert source.lookup_all("Haus") == ("hˈaʊs", "haʊs")


def test_crane_config_resolves_requested_cases() -> None:
    config = load_config(CONFIG)
    assert config.values["source"]["id"] == "crane_wiktionary"
    assert config.values["verification"] == {"required": True, "adversarial_misses": True}
    cases = config.values["cases"]
    assert [case["name"] for case in cases] == [
        "a0-v4-concat-control",
        "a1-v4-german-compound",
        "a2-v4-existing-strong",
        "a3-v4-existing-strong-utility",
    ]
    assert all(case["runtime"]["fresh_process"] for case in cases)
    strong = cases[2]
    assert strong["boundary_rules"] == "v2"
    assert strong["linkers"] == "german"
    assert strong["recursive_components"] is True
    assert strong["segmentation_scorer"] == "v2"
    utility = cases[3]
    assert utility["inherits"] == "a2-v4-existing-strong"
    assert utility["optimizer"] == "utility"
    assert utility["max_passes"] == 4


def test_network_free_crane_case_writes_lossless_runtime_artifacts(tmp_path: Path) -> None:
    config_path = tmp_path / "fixture.toml"
    config_path.write_text(
        f'''schema_version = 1
strict = true
seed = 1729
output = "{(tmp_path / "runs").as_posix()}"

[source]
id = "crane_wiktionary"
path = "{FIXTURE.as_posix()}"

[limits]
max_states = 100000
max_components = 4
max_recursive_depth = 4
target_literals = 400000

[verification]
required = true
adversarial_misses = true

[runtime]
fresh_process = true
sample_size = 5
repetitions = 1
finalist_repetitions = 1

[storage]
asset_format = "v4"
membership_backend = "dafsa-binary-v2"
literal_backend = "binary-pool-v2"
pronunciation_codec = "utf8"

[[cases]]
name = "crane-fixture-v4"
mode = "implicit-compound"
optimizer = "greedy"
selector = "v1"
boundary_rules = "v2"
linkers = "german"
recursive_components = true
segmentation_scorer = "v2"
''',
        encoding="utf-8",
    )
    results = run_config(config_path)
    assert len(results) == 1
    output = tmp_path / "runs" / "crane-fixture-v4"
    required = (
        "candidate.lxc",
        "verification.json",
        "summary.json",
        "build.json",
        "audit.json",
        "section-sizes.json",
        "runtime.json",
    )
    assert all((output / name).is_file() for name in required)
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["source_physical_rows"] == 9
    assert summary["source_logical_word_count"] == 9
    assert summary["source_ordered_variant_count"] == 9
    assert summary["source_duplicate_variant_rows_removed"] == 0
    assert summary["source_id"] == "crane_wiktionary"
    assert summary["source_format"] == "tsv_variants"
    assert summary["lossless"] is True
    assert summary["per_generated_word_recipe_count"] == 0
    assert summary["verification"]["missing_words"] == 0
    assert summary["verification"]["extra_words"] == 0
    assert summary["verification"]["pronunciation_mismatches"] == 0
    assert summary["verification"]["variant_order_mismatches"] == 0
    runtime = json.loads((output / "runtime.json").read_text(encoding="utf-8"))
    for key in (
        "baseline_rss_delta_bytes",
        "candidate_rss_delta_bytes",
        "rss_saved_bytes",
        "rss_saved_rate",
        "baseline_pss_delta_bytes",
        "candidate_pss_delta_bytes",
        "pss_saved_bytes",
        "pss_saved_rate",
    ):
        assert key in runtime
    assert runtime["runtime_repetitions"]["baseline"]
    assert runtime["runtime_repetitions"]["candidate"]
    audit = json.loads((output / "audit.json").read_text(encoding="utf-8"))
    assert audit["per_generated_word_recipe_count"] == 0
    assert audit["checked"] is True
    serialized = (output / "candidate.lxc").read_bytes()
    assert b"derived" not in serialized
    assert b"split_by_word" not in serialized
    assert b"generated_words" not in serialized
    leaderboard = aggregate(tmp_path / "runs")
    assert leaderboard["cases"] == 1
    row = leaderboard["leaderboard"][0]
    for field in (
        "source_physical_rows",
        "source_ordered_variant_count",
        "baseline_rss_delta_bytes",
        "candidate_rss_delta_bytes",
        "rss_saved_bytes",
        "rss_saved_rate",
    ):
        assert field in row
    assert (tmp_path / "runs" / "leaderboard.json").is_file()
    assert (tmp_path / "runs" / "leaderboard.tsv").is_file()
    assert (tmp_path / "runs" / "leaderboard.md").is_file()
    assert (tmp_path / "runs" / "pareto.json").is_file()


def test_aggregate_prefers_lossless_rows(tmp_path: Path) -> None:
    common = {
        "baseline_word_count": 10,
        "literal_word_count": 2,
        "generated_word_count": 8,
        "entry_reduction_rate": 0.8,
        "asset_bytes": 10,
        "lossless": True,
        "source_physical_rows": 10,
        "source_ordered_variant_count": 10,
    }
    (tmp_path / "lossless").mkdir()
    (tmp_path / "lossy").mkdir()
    (tmp_path / "lossless" / "summary.json").write_text(json.dumps(common), encoding="utf-8")
    (tmp_path / "lossy" / "summary.json").write_text(
        json.dumps({**common, "lossless": False, "literal_word_count": 1, "asset_bytes": 1}),
        encoding="utf-8",
    )
    result = aggregate(tmp_path)
    assert result["leaderboard"][0]["case"] == "lossless"
    assert all(row["case"] != "lossy" for row in result["pareto"])
