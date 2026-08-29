"""Compatibility tests for the semantic selector modules."""

from __future__ import annotations

from g2lex.runtime import ReconstructionCandidate
from g2lex.selectors import (
    CARTSelector,
    ForestSelector,
    GBDTSelector,
    GradientBoostedTreeSelector,
    HashedLogisticSelector,
    PrioritySelector,
    RandomForestSelector,
    StaticPrioritySelector,
    TreePredicate,
    TreeSelector,
)
from g2lex.selectors.forest import RandomForestSelector as ForestImplementation
from g2lex.selectors.gbdt import GradientBoostedTreeSelector as GBDTImplementation
from g2lex.selectors.logistic import HashedLogisticSelector as LogisticImplementation
from g2lex.selectors.priority import StaticPrioritySelector as PriorityImplementation
from g2lex.selectors.tree import TreeSelector as TreeImplementation


def test_selector_aliases_preserve_flat_import_surface() -> None:
    assert ForestSelector is RandomForestSelector is ForestImplementation
    assert GBDTSelector is GradientBoostedTreeSelector is GBDTImplementation
    assert PrioritySelector is StaticPrioritySelector is PriorityImplementation
    assert CARTSelector is TreeSelector is TreeImplementation
    assert HashedLogisticSelector is LogisticImplementation


def test_selector_serialization_and_choice_remain_deterministic() -> None:
    candidates = (
        ReconstructionCandidate("compound", ("x",), "r2", 2),
        ReconstructionCandidate("compound", ("x",), "r1", 1),
    )
    selector = StaticPrioritySelector()
    assert selector.choose({}, candidates) == candidates[1]
    assert selector.as_dict() == StaticPrioritySelector().as_dict()
    assert selector.serialized_bytes > 0
    assert (
        TreeSelector((TreePredicate("kind", "compound", "compound"),)).choose(
            {"kind": "compound"}, candidates
        )
        == candidates[1]
    )
