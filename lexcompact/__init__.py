"""Lossless resident-entry reduction for pronunciation lexicons."""

from __future__ import annotations

try:
    from ._version import __version__
except ImportError:  # defensive fallback for incomplete source trees
    __version__ = "0+unknown"

from .asset import ImplicitLexicon, load, load_traversable, loads, save
from .builder import BuildResult, build_implicit_lexicon
from .resolver import ComponentResolver, ResolveContext
from .segmentation import SegmentationScorer
from .io import LexiconFormatError, read_lexicon, write_lexicon
from .model import CandidateMetrics, LexiconData, LiteralLexicon, SourceInfo
from .reduce import ReductionConfig, reduce_file, reduce_lexicon
from .rules import ConcatenationRule, RuleSet, default_rules
from .verify import verify_candidate

__all__ = [
    "BuildResult",
    "CandidateMetrics",
    "ConcatenationRule",
    "ComponentResolver",
    "ImplicitLexicon",
    "LexiconData",
    "LexiconFormatError",
    "LiteralLexicon",
    "ReductionConfig",
    "ResolveContext",
    "RuleSet",
    "SegmentationScorer",
    "SourceInfo",
    "__version__",
    "build_implicit_lexicon",
    "default_rules",
    "load",
    "load_traversable",
    "loads",
    "read_lexicon",
    "reduce_file",
    "reduce_lexicon",
    "save",
    "verify_candidate",
    "write_lexicon",
]
