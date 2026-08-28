"""German shared rules reproduced from KokoroG2P's entry-reduction experiment."""

from __future__ import annotations

from ..boundary_rules import BoundaryStressClassRule, FinalComponentStressDemotionRule
from ..linkers import german_linker_table
from ..rules import default_rules


def german_rules(*, boundary_rules: bool = False, selector=None):
    """Return the experiment's shared German compound-stress rule set."""
    return default_rules(True, selector=selector, boundary_rules=boundary_rules)


__all__ = [
    "BoundaryStressClassRule",
    "FinalComponentStressDemotionRule",
    "german_linker_table",
    "german_rules",
]
