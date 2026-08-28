from pathlib import Path
import pytest
from benchmarks.de_lexicon_entry_reduction.download import destination, source_url
from benchmarks.de_lexicon_entry_reduction.download_sources import main
from benchmarks.de_lexicon_entry_reduction.sources import load_manifest


def test_manifest_pins_remote_sources():
    specs=load_manifest(); assert specs["gruut_espeak"].revision; assert specs["gruut_espeak"].values["sha256"]
    assert specs["crane_wiktionary"].revision; assert specs["crane_wiktionary"].values["sha256"]


def test_download_url_and_cache_are_revision_scoped(tmp_path: Path):
    spec=load_manifest()["gruut_espeak"]; url=source_url(spec); assert spec.revision in url and spec.filename in url
    assert spec.revision in str(destination(spec,tmp_path))


def test_downloader_requires_explicit_opt_in():
    with pytest.raises(SystemExit): main(["--source","gruut_espeak"])
