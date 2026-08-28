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
from .literals import (
    BinaryPoolLiteralStore,
    FSTLiteralStore,
    FrontCodedLiteralStore,
    InternedLiteralStore,
    LoudsFSTLiteralStore,
    RePairCodec,
    StringInterner,
    SymbolCodec,
    TokenSpacedCodec,
    VariantTupleInterner,
)
from .reduce import ReductionConfig, reduce_file, reduce_lexicon
from .membership import (
    BinaryDafsaMembership,
    BloomMembership,
    DafsaBinaryMembership,
    ExactMembership,
    MPHMembership,
    MembershipIndex,
    MarisaMembership,
    SortedUTF8Membership,
    XorFilterMembership,
)
from .neural import NeuralModel, NeuralReconstructor, train_gru, train_lstm, train_neural, train_transformer
from .selectors import (
    GBDTSelector,
    HashedLogisticSelector,
    RandomForestSelector,
    StaticPrioritySelector,
    TreeSelector,
    train_hashed_logistic,
)
from .g2p import CARTModel, CARTReconstructor, train_cart
from .graphone import GraphoneModel, GraphoneReconstructor, train_graphone
from .training.alignment import align, align_spelling
from .reconstructors import AffixRule, MorphologyReconstructor, RewriteReconstructor, RewriteRule, induce_rewrite_rules, mine_morphology
from .runtime import (
    CandidateSelector,
    OverlayMapping,
    ReconstructionCandidate,
    Reconstructor,
    ResolvedValues,
    RuntimeProgram,
)
from .rules import ConcatenationRule, RuleSet, default_rules
from .verify import verify_candidate

__all__ = [
    "BuildResult",
    "BinaryPoolLiteralStore",
    "GBDTSelector",
    "HashedLogisticSelector",
    "RandomForestSelector",
    "StaticPrioritySelector",
    "TreeSelector",
    "train_hashed_logistic",
    "NeuralModel",
    "NeuralReconstructor",
    "train_gru",
    "train_lstm",
    "train_neural",
    "train_transformer",
    "CARTModel",
    "CARTReconstructor",
    "GraphoneModel",
    "GraphoneReconstructor",
    "train_cart",
    "train_graphone",
    "align",
    "align_spelling",
    "AffixRule",
    "MorphologyReconstructor",
    "RewriteReconstructor",
    "RewriteRule",
    "induce_rewrite_rules",
    "mine_morphology",
    "FSTLiteralStore",
    "FrontCodedLiteralStore",
    "InternedLiteralStore",
    "LoudsFSTLiteralStore",
    "RePairCodec",
    "StringInterner",
    "SymbolCodec",
    "TokenSpacedCodec",
    "VariantTupleInterner",
    "MembershipIndex",
    "BinaryDafsaMembership",
    "BloomMembership",
    "DafsaBinaryMembership",
    "MPHMembership",
    "MarisaMembership",
    "SortedUTF8Membership",
    "XorFilterMembership",
    "CandidateSelector",
    "ExactMembership",
    "OverlayMapping",
    "ReconstructionCandidate",
    "Reconstructor",
    "ResolvedValues",
    "RuntimeProgram",
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
