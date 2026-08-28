"""Compatibility helpers for consumers such as KokoroG2P."""

from __future__ import annotations

from collections import namedtuple
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .asset import load, load_traversable
from .layers import CaseAliasMapping, LayeredLexicon, LexiconLayer
from .lexicon import open_lexicon, open_traversable
from .value import LexiconValue

LEXICON_PROFILES = {
    "en-us": {"default": ("us_gold", "us_silver"), "gold": ("us_gold",)},
    "en-gb": {"default": ("gb_gold", "gb_silver"), "gold": ("gb_gold",)},
    "de": {"default": ("de_gold",), "gold": ("de_gold",)},
    "fr": {"default": ("fr_gold",), "gold": ("fr_gold",)},
}

_CACHE: dict[object, Mapping[str, LexiconValue]] = {}
_CacheInfo = namedtuple("LexiconCacheInfo", "hits misses maxsize currsize")
_CACHE_HITS = 0
_CACHE_MISSES = 0


def open_kokoro_lexicon(resource: Any, *, aliases: bool = False, cache_key: object = None):
    """Open one packaged or filesystem G2Lex v1 lexicon, optionally with aliases."""

    global _CACHE_HITS, _CACHE_MISSES
    key = cache_key if cache_key is not None else resource
    if key in _CACHE:
        _CACHE_HITS += 1
        return _CACHE[key]
    _CACHE_MISSES += 1
    if isinstance(resource, (str, Path)):
        lexicon = open_lexicon(resource)
    else:
        lexicon = open_traversable(resource)
    result: Mapping[str, LexiconValue] = CaseAliasMapping(lexicon) if aliases else lexicon
    _CACHE[key] = result
    if len(_CACHE) > 4:
        oldest = next(iter(_CACHE))
        evicted = _CACHE.pop(oldest)
        close = getattr(evicted, "close", None)
        if close is not None:
            close()
    return result


def layer_kokoro_lexica(
    gold: Mapping[str, LexiconValue] | None = None,
    silver: Mapping[str, LexiconValue] | None = None,
    *,
    aliases: bool = False,
) -> LayeredLexicon:
    """Create explicit raw-record gold then silver precedence."""

    layers = []
    for name, mapping in (("gold", gold), ("silver", silver)):
        if mapping is not None:
            layers.append(LexiconLayer(name, CaseAliasMapping(mapping) if aliases else mapping, {}))
    return LayeredLexicon(layers)


def clear_lexicon_cache() -> None:
    global _CACHE_HITS, _CACHE_MISSES
    values = tuple(_CACHE.values())
    _CACHE.clear()
    _CACHE_HITS = _CACHE_MISSES = 0
    closed: set[int] = set()
    for mapping in values:
        close = getattr(mapping, "close", None)
        if close is not None and id(mapping) not in closed:
            close()
            closed.add(id(mapping))


def lexicon_cache_info():
    return _CacheInfo(_CACHE_HITS, _CACHE_MISSES, 4, len(_CACHE))


__all__ = [
    "LEXICON_PROFILES",
    "CaseAliasMapping",
    "LayeredLexicon",
    "LexiconLayer",
    "clear_lexicon_cache",
    "layer_kokoro_lexica",
    "lexicon_cache_info",
    "load",
    "load_traversable",
    "open_kokoro_lexicon",
]
