from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_cli_accepts_explicit_tsv_sources_and_conflict_limit(tmp_path: Path) -> None:
    left = tmp_path / "left.tsv"
    right = tmp_path / "right.tsv"
    left.write_text("Haus\th\nshared\ta\n", encoding="utf-8")
    right.write_text("haus\th\nshared\tb\n", encoding="utf-8")
    output = tmp_path / "report"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "benchmarks.lexicon_analysis.run",
            "--source",
            f"left={left}:tsv",
            "--source",
            f"right={right}:tsv",
            "--output",
            str(output),
            "--conflict-limit",
            "0",
            "--layer",
            "left",
            "--layer",
            "right",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["options"]["conflict_limit"] == 0
    assert summary["pairs"][0]["lowercase_key_intersection"] == 2
    assert summary["pairs"][0]["conflicts"] == []
    assert summary["layers"]["layers"] == ["left", "right"]
