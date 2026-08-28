"""Sketch of the minimal KokoroG2P German loader integration.

This file is intentionally not imported by lexcompact.  It documents the consumer-side
change: replace the resident JSON mapping with the mapping-compatible implicit lexicon.
"""

from __future__ import annotations

import importlib.resources

from lexcompact import load_traversable


def load_german_gold_asset(data_package) -> object:
    files = importlib.resources.files(data_package)
    return load_traversable(files / "de_gold.lxc")
