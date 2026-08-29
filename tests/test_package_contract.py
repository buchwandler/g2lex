"""Public package and distribution contract tests."""

from __future__ import annotations

import importlib.metadata
from importlib.resources import files

import g2lex
import g2lex.experimental


def test_public_exports_resolve() -> None:
    assert g2lex.__all__
    for name in g2lex.__all__:
        assert getattr(g2lex, name) is not None


def test_distribution_metadata_contract() -> None:
    metadata = importlib.metadata.metadata("g2lex")
    assert metadata["Name"] == "g2lex"
    assert metadata["Requires-Python"] == ">=3.10"
    requirements = importlib.metadata.requires("g2lex") or []
    assert all('extra ==' in requirement for requirement in requirements)
    assert metadata.get_all("Provides-Extra") == ["dev", "benchmark"]


def test_py_typed_is_packaged() -> None:
    assert files("g2lex").joinpath("py.typed").is_file()
