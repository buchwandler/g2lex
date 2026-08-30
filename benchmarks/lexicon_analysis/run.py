"""Run source-neutral analysis against explicit local sources.

Examples::

    python -m benchmarks.lexicon_analysis.run \
      --source crane=de.tsv:tsv --source gruut=de.g2lex \
      --output runs/de-analysis
"""

from __future__ import annotations

import argparse
from pathlib import Path

from g2lex import open as open_g2lex
from g2lex import read_typed_lexicon
from g2lex.layers import LexiconLayer

from .analysis import source_summary
from .cascade import evaluate_cascade
from .compare import cross_source_sharing, pairwise_sources
from .reporting import write_run


def _spec(value: str) -> tuple[str, Path, str | None]:
    try:
        name, location = value.split("=", 1)
    except ValueError as exc:
        raise ValueError("source must use NAME=PATH[:FORMAT]") from exc
    if not name:
        raise ValueError("source name must not be empty")
    path_text, separator, format_name = location.rpartition(":")
    if separator and format_name in {
        "tsv",
        "lxc-tsv",
        "json",
        "json-map",
        "jsonl",
        "cmudict",
        "mfa",
        "pls",
        "words",
    }:
        return name, Path(path_text), format_name
    return name, Path(location), None


def load_source(value: str):
    name, path, format_name = _spec(value)
    if path.suffix.lower() == ".g2lex":
        return name, open_g2lex(path)
    return name, read_typed_lexicon(path, format=format_name or "auto", source_id=name)


def run_analysis(
    sources: list[str],
    output: Path,
    *,
    conflict_limit: int = 1000,
    layer_order: list[str] | None = None,
    reference: str | None = None,
) -> dict[str, object]:
    loaded_items = [load_source(value) for value in sources]
    loaded = dict(loaded_items)
    source_rows = [source_summary(loaded[name], source_name=name) for name in sorted(loaded)]
    pairs = pairwise_sources(loaded, conflict_limit=conflict_limit)
    sharing = cross_source_sharing(loaded)
    ordered_names = layer_order or [name for name, _ in loaded_items]
    unknown = set(ordered_names) - set(loaded)
    if unknown:
        raise ValueError(f"unknown layer source(s): {', '.join(sorted(unknown))}")
    layers = [LexiconLayer(name, loaded[name], {}) for name in ordered_names]
    reference_mapping = None
    if reference:
        _, reference_source = load_source(reference)
        reference_mapping = getattr(reference_source, "entries", reference_source)
    cascade = evaluate_cascade(layers, reference=reference_mapping)
    summary = {
        "schema": 1,
        "sources": source_rows,
        "pairs": pairs,
        "cross_source_sharing": sharing,
        "layers": cascade,
        "options": {"conflict_limit": conflict_limit, "layer_order": ordered_names},
    }
    write_run(output, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", required=True, metavar="NAME=PATH[:FORMAT]")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--layer", action="append", dest="layers", help="Layer name, in precedence order"
    )
    parser.add_argument("--reference", metavar="NAME=PATH[:FORMAT]")
    parser.add_argument("--conflict-limit", type=int, default=1000)
    args = parser.parse_args()
    if args.conflict_limit < 0:
        parser.error("--conflict-limit must be non-negative")
    run_analysis(
        args.source,
        args.output,
        conflict_limit=args.conflict_limit,
        layer_order=args.layers,
        reference=args.reference,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
