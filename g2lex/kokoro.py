"""Deprecated compatibility helpers for consumers such as KokoroG2P.

New consumers should use :func:`g2lex.open_traversable` and
:class:`g2lex.LayeredLexicon` directly so resource and policy ownership remains
with the consumer.
"""

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

_CacheInfo = namedtuple("_CacheInfo", "hits misses maxsize currsize")
_CACHE_HITS = 0
_CACHE_MISSES = 0


def open_kokoro_lexicon(resource: Any, *, aliases: bool = False, cache_key: object = None):
    """Open one lexicon without retaining a caller-owned live handle.

    Deprecated: use :func:`g2lex.open_traversable` or :func:`g2lex.open` and
    manage the returned resource directly. ``cache_key`` is accepted for
    source compatibility but no live-object cache is maintained.
    """
    del cache_key
    global _CACHE_MISSES
    _CACHE_MISSES += 1
    if isinstance(resource, (str, Path)):
        lexicon = open_lexicon(resource)
    else:
        lexicon = open_traversable(resource)
    return CaseAliasMapping(lexicon) if aliases else lexicon


def layer_kokoro_lexica(
    gold: Mapping[str, LexiconValue] | None = None,
    silver: Mapping[str, LexiconValue] | None = None,
    *,
    aliases: bool = False,
) -> LayeredLexicon:
    """Create explicit raw-record gold then silver precedence.

    Deprecated compatibility helper; new consumers should construct layers
    directly with :class:`g2lex.LexiconLayer` and :class:`g2lex.LayeredLexicon`.
    """
    layers = []
    for name, mapping in (("gold", gold), ("silver", silver)):
        if mapping is not None:
            layers.append(LexiconLayer(name, CaseAliasMapping(mapping) if aliases else mapping, {}))
    return LayeredLexicon(layers)


def clear_lexicon_cache() -> None:
    """Reset compatibility cache counters; no live handles are retained."""
    global _CACHE_HITS, _CACHE_MISSES
    _CACHE_HITS = _CACHE_MISSES = 0


def lexicon_cache_info():
    """Report the disabled compatibility cache state."""
    return _CacheInfo(_CACHE_HITS, _CACHE_MISSES, 0, 0)


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
