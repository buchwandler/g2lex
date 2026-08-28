"""Lossless resident-entry reduction for pronunciation lexicons."""

from __future__ import annotations

try:
    from ._version import __version__
except ImportError:  # defensive fallback for incomplete source trees
    __version__ = "0+unknown"

from .asset import ImplicitLexicon, load, load_traversable, loads, save
from .builder import BuildResult, build_implicit_lexicon
from .g2p import CARTModel, CARTReconstructor, train_cart
from .graphone import GraphoneModel, GraphoneReconstructor, train_graphone
from .io import (
    LexiconFormatError,
    parse_typed_bytes,
    read_lexicon,
    read_typed_lexicon,
    write_lexicon,
)
from .kokoro import (
    LEXICON_PROFILES,
    clear_lexicon_cache,
    layer_kokoro_lexica,
    lexicon_cache_info,
    open_kokoro_lexicon,
)
from .layers import CaseAliasMapping, LayeredLexicon, LexiconLayer
from .lexicon import Lexicon, LexiconRecord, open, open_bytes, open_lexicon, open_traversable
from .literals import (
    BinaryPoolLiteralStore,
    FrontCodedLiteralStore,
    FSTLiteralStore,
    InternedLiteralStore,
    LoudsFSTLiteralStore,
    RePairCodec,
    StringInterner,
    SymbolCodec,
    TokenSpacedCodec,
    VariantTupleInterner,
)
from .membership import (
    BinaryDafsaMembership,
    BloomMembership,
    DafsaBinaryMembership,
    ExactMembership,
    MarisaMembership,
    MembershipIndex,
    MPHMembership,
    SortedUTF8Membership,
    XorFilterMembership,
)
from .model import CandidateMetrics, LexiconData, LiteralLexicon, SourceInfo, TypedLexiconData
from .neural import (
    NeuralModel,
    NeuralReconstructor,
    train_gru,
    train_lstm,
    train_neural,
    train_transformer,
)
from .operations import export_file, inspect_file, pack_file, verify_file
from .reconstructors import (
    AffixRule,
    MorphologyReconstructor,
    RewriteReconstructor,
    RewriteRule,
    induce_rewrite_rules,
    mine_morphology,
)
from .reduce import ReductionConfig, reduce_file, reduce_lexicon
from .resolver import ComponentResolver, ResolveContext
from .rules import ConcatenationRule, RuleSet, default_rules
from .runtime import (
    CandidateSelector,
    OverlayMapping,
    ReconstructionCandidate,
    Reconstructor,
    ResolvedValues,
    RuntimeProgram,
)
from .segmentation import SegmentationScorer
from .selectors import (
    GBDTSelector,
    HashedLogisticSelector,
    RandomForestSelector,
    StaticPrioritySelector,
    TreeSelector,
    train_hashed_logistic,
)
from .training.alignment import align, align_spelling
from .value import WORD_ONLY, LexiconValue, TaggedValue, logical_sha256
from .verify import verify_candidate
from .verify_v5 import LexiconDiff, compare, verify_typed

__all__ = [
    "LEXICON_PROFILES",
    "WORD_ONLY",
    "AffixRule",
    "BinaryDafsaMembership",
    "BinaryPoolLiteralStore",
    "BloomMembership",
    "BuildResult",
    "CARTModel",
    "CARTReconstructor",
    "CandidateMetrics",
    "CandidateSelector",
    "CaseAliasMapping",
    "ComponentResolver",
    "ConcatenationRule",
    "DafsaBinaryMembership",
    "ExactMembership",
    "FSTLiteralStore",
    "FrontCodedLiteralStore",
    "GBDTSelector",
    "GraphoneModel",
    "GraphoneReconstructor",
    "HashedLogisticSelector",
    "ImplicitLexicon",
    "InternedLiteralStore",
    "LayeredLexicon",
    "Lexicon",
    "LexiconData",
    "LexiconDiff",
    "LexiconFormatError",
    "LexiconLayer",
    "LexiconRecord",
    "LexiconValue",
    "LiteralLexicon",
    "LoudsFSTLiteralStore",
    "MPHMembership",
    "MarisaMembership",
    "MembershipIndex",
    "MorphologyReconstructor",
    "NeuralModel",
    "NeuralReconstructor",
    "OverlayMapping",
    "RandomForestSelector",
    "RePairCodec",
    "ReconstructionCandidate",
    "Reconstructor",
    "ReductionConfig",
    "ResolveContext",
    "ResolvedValues",
    "RewriteReconstructor",
    "RewriteRule",
    "RuleSet",
    "RuntimeProgram",
    "SegmentationScorer",
    "SortedUTF8Membership",
    "SourceInfo",
    "StaticPrioritySelector",
    "StringInterner",
    "SymbolCodec",
    "TaggedValue",
    "TokenSpacedCodec",
    "TreeSelector",
    "TypedLexiconData",
    "VariantTupleInterner",
    "XorFilterMembership",
    "__version__",
    "align",
    "align_spelling",
    "build_implicit_lexicon",
    "clear_lexicon_cache",
    "compare",
    "default_rules",
    "export_file",
    "induce_rewrite_rules",
    "inspect_file",
    "layer_kokoro_lexica",
    "lexicon_cache_info",
    "load",
    "load_traversable",
    "loads",
    "logical_sha256",
    "mine_morphology",
    "open",
    "open_bytes",
    "open_kokoro_lexicon",
    "open_lexicon",
    "open_traversable",
    "pack_file",
    "parse_typed_bytes",
    "read_lexicon",
    "read_typed_lexicon",
    "reduce_file",
    "reduce_lexicon",
    "save",
    "train_cart",
    "train_graphone",
    "train_gru",
    "train_hashed_logistic",
    "train_lstm",
    "train_neural",
    "train_transformer",
    "verify_candidate",
    "verify_file",
    "verify_typed",
    "write_lexicon",
]
