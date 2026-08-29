"""Regression tests for documentation build path isolation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


@pytest.mark.parametrize("cwd", (ROOT, DOCS))
def test_docs_conf_does_not_shadow_stdlib_selectors(cwd: Path) -> None:
    code = f"""
import runpy
from pathlib import Path

runpy.run_path({str(DOCS / "conf.py")!r})
import selectors

selectors_path = Path(selectors.__file__).resolve()
project_package = (Path({str(ROOT)!r}) / "g2lex").resolve()
assert project_package not in selectors_path.parents, selectors_path
"""
    completed = subprocess.run(
        [sys.executable, "-S", "-c", code],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
