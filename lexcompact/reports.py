"""Stable reduction summaries."""

from __future__ import annotations

from typing import Any

from .builder import BuildResult


def summary_dict(build: BuildResult, *, verification: dict[str, Any] | None = None, asset_bytes: int | None = None) -> dict[str, Any]:
    metrics = build.metrics
    result: dict[str, Any] = {
        "baseline_word_count": metrics.baseline_word_count,
        "literal_word_count": metrics.literal_word_count,
        "generated_word_count": metrics.generated_word_count,
        "entry_reduction_count": metrics.entry_reduction_count,
        "entry_reduction_rate": metrics.entry_reduction_rate,
        "per_generated_word_recipe_count": metrics.per_generated_word_recipe_count,
        "membership_state_count": int(getattr(build.asset.membership, "state_count", 0)),
        "membership_edge_count": int(getattr(build.asset.membership, "edge_count", 0)),
        "membership_serialized_bytes": build.asset.membership.serialized_bytes,
        "literal_index_state_count": build.asset.literal_index.state_count,
        "search_limit_words": build.search_limit_words,
        "membership_enumeration_matches": build.membership_enumeration_matches,
        "target_literal_word_count": int(build.asset.metadata.get("target_literal_word_count", 400_000)),
        "stage_coverage": build.telemetry.get("stages", {}),
        "build_telemetry": build.telemetry,
        "membership_backend": getattr(build.asset.membership, "backend_id", "unknown"),
        "literal_backend": getattr(build.asset.literals, "backend_id", "unknown"),
        "pronunciation_codec": build.asset.metadata.get("pronunciation_codec", {"id": "utf8"}),
    }
    result["target_met"] = result["literal_word_count"] <= result["target_literal_word_count"]
    if verification is not None:
        result["verification"] = verification
        result["lossless"] = bool(verification.get("lossless"))
    if asset_bytes is not None:
        result["asset_bytes"] = asset_bytes
    return result


def report_markdown(summary: dict[str, Any]) -> str:
    verification = summary.get("verification") or {}
    return f"""# Lexicon resident-entry reduction result

Baseline logical words: {int(summary['baseline_word_count']):,}
Candidate literal words: {int(summary['literal_word_count']):,}
Implicitly generated baseline words: {int(summary['generated_word_count']):,}
Literal-entry reduction: {float(summary['entry_reduction_rate']):.2%}
Target: <= {int(summary['target_literal_word_count']):,}
Target met: {'yes' if summary.get('target_met') else 'no'}
Per-generated-word runtime recipes: {int(summary['per_generated_word_recipe_count'])}

Lossless verification:
- words checked: {int(verification.get('words_checked', 0)):,}
- missing: {int(verification.get('missing_words', 0)):,}
- extra membership hits: {int(verification.get('extra_words', 0)):,}
- pronunciation mismatches: {int(verification.get('pronunciation_mismatches', 0)):,}
- variant-order mismatches: {int(verification.get('variant_order_mismatches', 0)):,}
- lossless: {'yes' if verification.get('lossless') else 'not verified'}
"""
