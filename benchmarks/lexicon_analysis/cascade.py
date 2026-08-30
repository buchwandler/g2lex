"""Analysis of production G2Lex layer precedence."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence

from g2lex.layers import LayeredLexicon, LayerHit, LexiconLayer


def _value_for_reference(value: object) -> object:
    return value


def _references(
    reference: Mapping[str, object] | Iterable[tuple[str, object]] | None,
) -> dict[str, object]:
    if reference is None:
        return {}
    return dict(reference)


def evaluate_cascade(
    layers: Sequence[LexiconLayer] | LayeredLexicon,
    words: Iterable[str] | None = None,
    *,
    reference: Mapping[str, object] | Iterable[tuple[str, object]] | None = None,
) -> dict[str, object]:
    """Evaluate an ordered cascade through :class:`LayeredLexicon` itself."""
    if isinstance(layers, LayeredLexicon):
        layered = layers
        layer_list = layered.layers
    else:
        layer_list = tuple(layers)
        layered = LayeredLexicon(layer_list)
    if words is None:
        evaluated = sorted({word for layer in layer_list for word in layer.lexicon})
    else:
        evaluated = sorted(set(words))
    expected = _references(reference)
    hits_by_source: Counter[str] = Counter()
    incremental_hits: Counter[str] = Counter()
    conflict_wins: Counter[str] = Counter()
    incremental_exact: Counter[str] = Counter()
    incremental_errors: Counter[str] = Counter()
    selected_exact = oracle_exact = fallback = 0
    rows: list[dict[str, object]] = []
    for word in evaluated:
        hit: LayerHit | None = layered.get_hit(word)
        missing = object()
        all_hits = []
        for layer in layer_list:
            value = layer.lexicon.get(word, missing)
            if value is not missing:
                all_hits.append((layer.name, value))
        for name, _ in all_hits:
            hits_by_source[name] += 1
        selected = hit.value if hit is not None else None
        selected_name = hit.name if hit is not None else None
        if hit is None:
            fallback += 1
        else:
            incremental_hits[hit.name] += 1
        conflict = len({repr(value) for _, value in all_hits}) > 1
        if conflict and selected_name is not None:
            conflict_wins[selected_name] += 1
        row: dict[str, object] = {
            "word": word,
            "selected_source": selected_name,
            "selected_value": selected,
            "hit_sources": [name for name, _ in all_hits],
            "conflict": conflict,
        }
        if word in expected:
            is_exact = hit is not None and selected == _value_for_reference(expected[word])
            oracle = any(value == expected[word] for _, value in all_hits)
            selected_exact += is_exact
            oracle_exact += oracle
            if selected_name is not None:
                (incremental_exact if is_exact else incremental_errors)[selected_name] += 1
            row.update({"selected_exact_match": is_exact, "oracle_exact_match": oracle})
        rows.append(row)
    total = len(evaluated)
    reference_count = len(expected)
    return {
        "layers": [layer.name for layer in layer_list],
        "total_evaluated_words": total,
        "coverage": (total - fallback) / total if total else 0.0,
        "hits_by_source": dict(sorted(hits_by_source.items())),
        "incremental_hits_by_source": dict(sorted(incremental_hits.items())),
        "conflict_wins_by_source": dict(sorted(conflict_wins.items())),
        "fallback_miss_count": fallback,
        "reference_entries": reference_count,
        "selected_exact_match": selected_exact if expected else None,
        "oracle_any_layer_exact_match": oracle_exact if expected else None,
        "incremental_exact_matches_by_source": dict(sorted(incremental_exact.items())),
        "incremental_errors_by_source": dict(sorted(incremental_errors.items())),
        "rows": rows,
    }


__all__ = ["evaluate_cascade"]
