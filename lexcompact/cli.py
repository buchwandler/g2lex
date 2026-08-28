"""Command-line interface for lexcompact."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .asset import load, runtime_asset_bytes, save
from .io import LexiconData, read_lexicon, write_lexicon
from .model import SourceInfo
from .profiles.german import german_linker_table, german_rules
from .reduce import ReductionConfig, reduce_lexicon
from .reports import report_markdown, summary_dict
from .rules import default_rules
from .segmentation import SegmentationScorer
from .verify import verify_candidate

try:
    from ._version import __version__
except ImportError:
    __version__ = "0+unknown"


def _profile(name: str):
    if name == "generic":
        return default_rules(False), None
    if name == "de-compound":
        return german_rules(boundary_rules=False), None
    if name == "de-boundary":
        return german_rules(boundary_rules=True), None
    if name == "de-linkers":
        return german_rules(boundary_rules=False), german_linker_table()
    raise ValueError(f"unknown profile: {name}")


def _cmd_reduce(args: argparse.Namespace) -> int:
    source = read_lexicon(args.source, format=args.format)
    rules, linkers = _profile(args.profile)
    scorer = SegmentationScorer() if args.segmentation_scorer == "v2" else None
    config = ReductionConfig(
        max_components=args.max_components,
        max_states=args.max_states,
        target_literals=args.target_literals,
        optimizer=args.optimizer,
        max_passes=args.max_passes,
        recursive_components=args.recursive_components,
        max_recursive_depth=args.max_recursive_depth,
        segmentation_scorer=scorer,
    )
    result = reduce_lexicon(source, config=config, rules=rules, linkers=linkers)
    save(args.output, result.asset)
    verification = verify_candidate(result.asset, source)
    summary = summary_dict(
        result,
        verification=verification,
        asset_bytes=runtime_asset_bytes(args.output),
    )
    if args.report:
        Path(args.report).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if verification["lossless"] else 1


def _cmd_verify(args: argparse.Namespace) -> int:
    source = read_lexicon(args.source, format=args.format)
    candidate = load(args.asset)
    result = verify_candidate(candidate, source)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["lossless"] else 1


def _cmd_lookup(args: argparse.Namespace) -> int:
    candidate = load(args.asset)
    values = candidate.lookup_all(args.word)
    if not values:
        return 1
    for value in values:
        print(value)
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    candidate = load(args.asset)
    summary = {
        **asdict(candidate.metrics()),
        "membership_state_count": candidate.membership.state_count,
        "membership_edge_count": candidate.membership.edge_count,
        "membership_serialized_bytes": candidate.membership.serialized_bytes,
        "asset_bytes": runtime_asset_bytes(args.asset),
        "source": asdict(candidate.source),
        "rules": candidate.composer.rules.as_dict(),
        "linkers": candidate.composer.linkers.as_dict() if candidate.composer.linkers else None,
        "recursive_components": candidate.composer.recursive_components,
        "max_recursive_depth": candidate.composer.max_recursive_depth,
        "segmentation_scorer": (
            candidate.composer.segmentation_scorer.as_dict()
            if candidate.composer.segmentation_scorer
            else None
        ),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _cmd_restore(args: argparse.Namespace) -> int:
    candidate = load(args.asset)
    entries = {word: candidate.lookup_all(word) for word in candidate}
    lexicon = LexiconData(entries, SourceInfo("restored"))
    write_lexicon(args.output, lexicon, format=args.format)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lexcompact",
        description="Losslessly reduce resident pronunciation-lexicon entries.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    reduce_p = sub.add_parser("reduce", help="build a reduced runtime asset")
    reduce_p.add_argument("source", type=Path)
    reduce_p.add_argument("output", type=Path)
    reduce_p.add_argument("--format", choices=("auto", "json", "tsv"), default="auto")
    reduce_p.add_argument(
        "--profile",
        choices=("generic", "de-compound", "de-boundary", "de-linkers"),
        default="generic",
        help="shared runtime rule profile; generic is language-neutral",
    )
    reduce_p.add_argument("--max-components", type=int, default=4)
    reduce_p.add_argument("--max-states", type=int, default=100_000)
    reduce_p.add_argument("--target-literals", type=int, default=400_000)
    reduce_p.add_argument("--optimizer", choices=("greedy", "utility"), default="greedy")
    reduce_p.add_argument("--max-passes", type=int, default=4)
    reduce_p.add_argument(
        "--recursive-components",
        action="store_true",
        help="allow known generated words to be ephemeral constituents of other words",
    )
    reduce_p.add_argument("--max-recursive-depth", type=int, default=4)
    reduce_p.add_argument(
        "--segmentation-scorer",
        choices=("v1", "v2"),
        default="v1",
        help="v1 uses historical ranking; v2 enables the compact integer scorer",
    )
    reduce_p.add_argument("--report", type=Path)
    reduce_p.set_defaults(func=_cmd_reduce)

    verify_p = sub.add_parser("verify", help="compare an asset to its original lexicon")
    verify_p.add_argument("source", type=Path)
    verify_p.add_argument("asset", type=Path)
    verify_p.add_argument("--format", choices=("auto", "json", "tsv"), default="auto")
    verify_p.set_defaults(func=_cmd_verify)

    lookup_p = sub.add_parser("lookup", help="look up one spelling")
    lookup_p.add_argument("asset", type=Path)
    lookup_p.add_argument("word")
    lookup_p.set_defaults(func=_cmd_lookup)

    inspect_p = sub.add_parser("inspect", help="show asset metrics")
    inspect_p.add_argument("asset", type=Path)
    inspect_p.set_defaults(func=_cmd_inspect)

    restore_p = sub.add_parser("restore", help="materialize the full logical lexicon")
    restore_p.add_argument("asset", type=Path)
    restore_p.add_argument("output", type=Path)
    restore_p.add_argument("--format", choices=("auto", "json", "tsv"), default="auto")
    restore_p.set_defaults(func=_cmd_restore)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
