"""Experimental resident-entry reduction and reconstruction APIs.

These APIs are not part of the stable G2Lex exact-runtime surface.
"""

from __future__ import annotations

from ..asset import ImplicitLexicon, load, load_traversable, loads, save
from ..builder import BuildResult, build_implicit_lexicon
from ..g2p import CARTModel, CARTReconstructor, train_cart
from ..graphone import GraphoneModel, GraphoneReconstructor, train_graphone
from ..model import CandidateMetrics, LexiconData, LiteralLexicon
from ..neural import (
    NeuralModel,
    NeuralReconstructor,
    train_gru,
    train_lstm,
    train_neural,
    train_transformer,
)
from ..reconstructors import (
    AffixRule,
    MorphologyReconstructor,
    RewriteReconstructor,
    RewriteRule,
    induce_rewrite_rules,
    mine_morphology,
)
from ..reduce import ReductionConfig, reduce_file, reduce_lexicon
from ..resolver import ComponentResolver, ResolveContext
from ..rules import ConcatenationRule, RuleSet, default_rules
from ..runtime import (
    CandidateSelector,
    OverlayMapping,
    ReconstructionCandidate,
    Reconstructor,
    ResolvedValues,
    RuntimeProgram,
)
from ..segmentation import SegmentationScorer
from ..selector import Candidate, RuleSelector
from ..selectors import (
    GBDTSelector,
    HashedLogisticSelector,
    RandomForestSelector,
    StaticPrioritySelector,
    TreeSelector,
    train_hashed_logistic,
)
from ..training.alignment import align, align_spelling
from ..verify import verify_candidate

__all__ = [
    "AffixRule",
    "BuildResult",
    "CARTModel",
    "CARTReconstructor",
    "Candidate",
    "CandidateMetrics",
    "CandidateSelector",
    "ComponentResolver",
    "ConcatenationRule",
    "GBDTSelector",
    "GraphoneModel",
    "GraphoneReconstructor",
    "HashedLogisticSelector",
    "ImplicitLexicon",
    "LexiconData",
    "LiteralLexicon",
    "MorphologyReconstructor",
    "NeuralModel",
    "NeuralReconstructor",
    "OverlayMapping",
    "RandomForestSelector",
    "ReconstructionCandidate",
    "Reconstructor",
    "ReductionConfig",
    "ResolveContext",
    "ResolvedValues",
    "RewriteReconstructor",
    "RewriteRule",
    "RuleSelector",
    "RuleSet",
    "RuntimeProgram",
    "SegmentationScorer",
    "StaticPrioritySelector",
    "TreeSelector",
    "align",
    "align_spelling",
    "build_implicit_lexicon",
    "default_rules",
    "induce_rewrite_rules",
    "load",
    "load_traversable",
    "loads",
    "mine_morphology",
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
]
