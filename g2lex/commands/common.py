"""Shared command parsing helpers."""

from __future__ import annotations

from ..profiles.german import german_linker_table, german_rules
from ..rules import default_rules
from ..value import WORD_ONLY, TaggedValue, as_plain_selector

MISSING = object()


def profile(name: str):
    if name == "generic":
        return default_rules(False), None
    if name == "de-compound":
        return german_rules(boundary_rules=False), None
    if name == "de-boundary":
        return german_rules(boundary_rules=True), None
    if name == "de-linkers":
        return german_rules(boundary_rules=False), german_linker_table()
    raise ValueError(f"unknown profile: {name}")


def plain_lookup(value):
    if value is WORD_ONLY:
        return {"kind": "word"}
    if isinstance(value, TaggedValue):
        return {
            "kind": "tagged",
            "items": [[tag, as_plain_selector(item)] for tag, item in value.items],
        }
    if isinstance(value, tuple):
        return list(value)
    return value
