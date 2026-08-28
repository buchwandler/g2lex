"""High-level reduction API."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .asset import save
from .builder import BuildResult, build_implicit_lexicon
from .composer import ImplicitComposer
from .io import read_lexicon
from .linkers import LinkerTable
from .model import LexiconData
from .optimizer import OptimizationResult, optimize_basis
from .rules import RuleSet, default_rules
from .segmentation import SegmentationScorer


@dataclass(frozen=True, slots=True)
class ReductionConfig:
    """Language-neutral offline/runtime reduction controls."""

    max_components: int = 4
    max_states: int = 100_000
    target_literals: int = 400_000
    optimizer: str = "greedy"
    max_passes: int = 4
    recursive_components: bool = False
    max_recursive_depth: int = 4
    segmentation_scorer: SegmentationScorer | None = None


def reduce_lexicon(
    source: LexiconData,
    *,
    config: ReductionConfig | None = None,
    rules: RuleSet | None = None,
    linkers: LinkerTable | None = None,
) -> BuildResult:
    """Build an exact implicit lexicon.

    The default rule set is plain pronunciation concatenation and is language-neutral.
    Language-specific shared transformations must be supplied explicitly.

    When ``recursive_components`` is enabled, generated constituents are resolved
    ephemerally at lookup time. They are never stored as per-word runtime recipes.
    """
    cfg = config or ReductionConfig()
    chosen_rules = rules or default_rules(False)
    if cfg.optimizer == "utility":
        composer = ImplicitComposer(
            max_components=cfg.max_components,
            max_states=cfg.max_states,
            rules=chosen_rules,
            linkers=linkers,
            recursive_components=cfg.recursive_components,
            max_recursive_depth=cfg.max_recursive_depth,
            segmentation_scorer=cfg.segmentation_scorer,
        )
        optimized: OptimizationResult = optimize_basis(
            source,
            composer=composer,
            rules=chosen_rules,
            linkers=linkers,
            recursive_components=cfg.recursive_components,
            max_recursive_depth=cfg.max_recursive_depth,
            max_components=cfg.max_components,
            max_states=cfg.max_states,
            segmentation_scorer=cfg.segmentation_scorer,
            max_passes=cfg.max_passes,
            target_literals=cfg.target_literals,
        )
        result = optimized.build
    elif cfg.optimizer == "greedy":
        result = build_implicit_lexicon(
            source,
            rules=chosen_rules,
            max_components=cfg.max_components,
            max_states=cfg.max_states,
            linkers=linkers,
            recursive_components=cfg.recursive_components,
            max_recursive_depth=cfg.max_recursive_depth,
            segmentation_scorer=cfg.segmentation_scorer,
        )
    else:
        raise ValueError(f"unknown optimizer: {cfg.optimizer!r}")
    result.asset.metadata["target_literal_word_count"] = cfg.target_literals
    return result


def reduce_file(
    source_path: str | Path,
    output_path: str | Path,
    *,
    input_format: str = "auto",
    config: ReductionConfig | None = None,
    rules: RuleSet | None = None,
    linkers: LinkerTable | None = None,
) -> BuildResult:
    source = read_lexicon(source_path, format=input_format)
    result = reduce_lexicon(source, config=config, rules=rules, linkers=linkers)
    save(output_path, result.asset)
    return result
