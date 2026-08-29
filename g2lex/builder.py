"""Offline construction of an implicit literal basis."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from .backends import build_codec, build_literal_store, build_membership_backend
from .composer import ImplicitComposer
from .linkers import LinkerTable
from .model import CandidateMetrics, ImplicitLexicon, LexiconData
from .prefix_index import MutableLiteralPrefixIndex
from .resolver import ComponentResolver, ResolveContext
from .rules import RuleSet
from .search import SearchLimitError


@dataclass(slots=True)
class BuildResult:
    asset: ImplicitLexicon
    metrics: CandidateMetrics
    failures: list[dict[str, Any]] = field(default_factory=list)
    membership_enumeration_matches: bool = True
    search_limit_words: int = 0
    telemetry: dict[str, Any] = field(default_factory=dict)


def build_implicit_lexicon(
    source: LexiconData,
    *,
    composer: ImplicitComposer | None = None,
    rules: RuleSet | None = None,
    max_components: int = 4,
    max_states: int = 100_000,
    forced_literals: Iterable[str] = (),
    linkers: LinkerTable | None = None,
    recursive_components: bool = False,
    max_recursive_depth: int = 4,
    segmentation_scorer: Any | None = None,
    membership_backend: str = "dafsa-json-v1",
    literal_backend: str = "dict-json-v3",
    pronunciation_codec: str = "utf8",
    seed: int = 0,
    codec_options: dict[str, Any] | None = None,
) -> BuildResult:
    """Build a candidate, using source IPA only for the offline keep decision."""

    if composer is None:
        composer = ImplicitComposer(
            max_components=max_components,
            max_states=max_states,
            rules=rules or RuleSet(),
            linkers=linkers,
            recursive_components=recursive_components,
            max_recursive_depth=max_recursive_depth,
            segmentation_scorer=segmentation_scorer,
        )
    elif rules is not None:
        composer.rules = rules
    if linkers is not None:
        composer.linkers = linkers
    if recursive_components:
        composer.recursive_components = True
        composer.max_recursive_depth = max_recursive_depth
    if segmentation_scorer is not None:
        composer.segmentation_scorer = segmentation_scorer
    forced = set(forced_literals)
    literals: dict[str, tuple[str, ...]] = {}
    prefix_index = MutableLiteralPrefixIndex.empty()
    failures: list[dict[str, Any]] = []
    generated_count = 0
    search_limit_words = 0

    membership = build_membership_backend(membership_backend, source.words, seed=seed)
    resolver = (
        ComponentResolver(
            membership,
            composer,
            literals,
            prefix_index,
            max_depth=max_recursive_depth,
            max_states=max_states,
        )
        if recursive_components
        else None
    )
    ordered_words = sorted(source.words, key=lambda word: (len(word), word))
    stage_coverage: dict[str, dict[str, int]] = {}

    def count(stage: str, field_name: str) -> None:
        values = stage_coverage.setdefault(stage, {})
        values[field_name] = values.get(field_name, 0) + 1

    for word in ordered_words:
        expected = source.lookup_all(word)
        result = None
        if word not in forced:
            try:
                result = composer.derive_result(
                    word,
                    literals=literals,
                    prefix_index=prefix_index,
                    resolver=resolver,
                    context=ResolveContext() if resolver is not None else None,
                )
            except SearchLimitError as exc:
                search_limit_words += 1
                failures.append(
                    {
                        "word": word,
                        "reason": "search-limit",
                        "error": str(exc),
                        "candidate": None,
                    }
                )
                count("compound", "candidate_budget_exhausted")
        if result is not None and result.pronunciation == expected:
            count("compound", "candidate_proposed")
            count("compound", "candidate_exact")
            count("compound", "candidate_selected")
            count("compound", "word_omitted")
            count("compound", "word_uniquely_unlocked")
            generated_count += 1
            composer.rules.record_result(result.rule_id, True)
            continue

        if result is not None:
            count("compound", "candidate_proposed")
            count("compound", "candidate_conflict")
            count("compound", "retained_selected_candidate_wrong")
            composer.rules.record_result(result.rule_id, False)
        if result is None and word not in forced:
            count("compound", "retained_no_candidate")
        literals[word] = expected
        prefix_index.add(word)
        if word not in forced:
            failures.append(
                {
                    "word": word,
                    "reason": "pronunciation-mismatch" if result else "no-composition",
                    "candidate": result.pronunciation if result else None,
                    "candidate_components": result.components if result else None,
                    "candidate_rule": result.rule_id if result else None,
                    "candidate_depth": len(result.components) if result else None,
                }
            )

    enumeration_matches = tuple(membership.iter_words()) == tuple(sorted(source.words))
    codec_options = codec_options or {}
    codec_values = (
        token
        for values in source.entries.values()
        for pronunciation in values
        for token in (
            pronunciation.split(" ") if pronunciation_codec == "token-spaced" else pronunciation
        )
    )
    codec = build_codec(pronunciation_codec, codec_values, **codec_options)
    codec_metadata: dict[str, object] = {"id": pronunciation_codec}
    if codec is not None and pronunciation_codec == "repair":
        payload = "\n".join(value for values in source.entries.values() for value in values).encode(
            "utf-8"
        )
        codec_metadata.update(codec.accounting(payload))
    metadata: dict[str, object] = {
        "schema": 1,
        "kind": "implicit-entry-reduction",
        "baseline_word_count": len(source.entries),
        "generated_word_count": generated_count,
        "per_generated_word_recipe_count": 0,
        "target_literal_word_count": 400_000,
        "composer_version": composer.rules.composer_version,
        "membership_version": 1,
        "rule_version": "1",
        "search_limit_words": search_limit_words,
        "membership_enumeration_matches": enumeration_matches,
        "membership_backend": membership.backend_id,
        "literal_backend": literal_backend,
        "pronunciation_codec": codec_metadata,
    }
    asset = ImplicitLexicon(
        source=source.source,
        literals=build_literal_store(literal_backend, literals, codec=codec),
        literal_index=prefix_index.freeze(),
        membership=membership,
        composer=composer,
        metadata=metadata,
    )
    return BuildResult(
        asset,
        CandidateMetrics(len(source.entries), len(literals), generated_count),
        failures,
        enumeration_matches,
        search_limit_words,
        {
            "stages": stage_coverage,
            "candidate_count": sum(
                item.get("candidate_proposed", 0) for item in stage_coverage.values()
            ),
            "generated_count": generated_count,
            "search_limit_words": search_limit_words,
        },
    )
