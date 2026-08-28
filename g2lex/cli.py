"""Command-line interface for g2lex."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .asset import load, runtime_asset_bytes, save
from .io import LexiconData, read_lexicon, write_lexicon
from .lexicon import open_lexicon
from .model import SourceInfo
from .operations import convert_file, export_file, inspect_file, pack_file, verify_file
from .profiles.german import german_linker_table, german_rules
from .reduce import ReductionConfig, reduce_lexicon
from .reports import summary_dict
from .rules import default_rules
from .segmentation import SegmentationScorer
from .value import WORD_ONLY, TaggedValue, as_plain_selector
from .verify import verify_candidate
from .verify_exact import compare

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
        result, verification=verification, asset_bytes=runtime_asset_bytes(args.output)
    )
    if args.report:
        args.report.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if verification["lossless"] else 1


def _cmd_pack(args: argparse.Namespace) -> int:
    metadata = {
        key: value
        for key, value in {
            "source_id": args.source_id,
            "display_name": args.display_name,
            "language": args.language,
            "locale": args.locale,
            "dialect": args.dialect,
            "tier": args.tier,
            "provider": args.provider,
            "revision": args.revision,
            "source_url": args.source_url,
            "pronunciation_alphabet": args.pronunciation_alphabet,
            "pronunciation_separator": args.pronunciation_separator,
            "role_namespace": args.role_namespace,
            "license_expression": args.license_expression,
            "license_name": args.license_name,
            "license_url": args.license_url,
            "attribution": args.attribution,
            "generator": args.generator,
            "parser_id": args.parser_id,
            "parser_version": args.parser_version,
        }.items()
        if value is not None
    }
    summary = pack_file(
        args.source,
        args.output,
        input_format=args.format,
        source_id=args.source_id,
        metadata=metadata,
        record_block_entries=args.record_block_entries,
        key_block_entries=args.key_block_entries,
        compression=args.compression,
        compression_level=args.compression_level,
    )
    if args.report:
        args.report.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    if args.asset.read_bytes()[:4] != b"G2LX":
        raise ValueError(
            "verify accepts G2Lex v1 assets; use 'experimental verify-reduced' for reduction assets"
        )
    result = verify_file(args.source, args.asset, input_format=args.format)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["lossless"] else 1


def _cmd_verify_reduced(args: argparse.Namespace) -> int:
    source = read_lexicon(args.source, format=args.format)
    candidate = load(args.asset)
    try:
        result = verify_candidate(candidate, source)
    finally:
        close = getattr(candidate, "close", None)
        if close is not None:
            close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["lossless"] else 1


def _plain_lookup(value):
    if value is WORD_ONLY:
        return {"kind": "word"}
    if isinstance(value, TaggedValue):
        return {
            "kind": "tagged",
            "items": [[tag, as_plain_selector(item)] for tag, item in value.items],
        }
    if isinstance(value, tuple):
        return list(value)
    return value


def _cmd_lookup(args: argparse.Namespace) -> int:
    if args.asset.read_bytes()[:4] != b"G2LX":
        candidate = load(args.asset)
        values = candidate.lookup_all(args.word)
        if not values:
            return 1
        for value in values:
            print(value)
        return 0
    candidate = open_lexicon(args.asset)
    try:
        value = candidate.get(args.word, _MISSING)
        if value is _MISSING:
            return 1
        print(json.dumps(_plain_lookup(value), ensure_ascii=False))
        return 0
    finally:
        candidate.close()


def _cmd_inspect(args: argparse.Namespace) -> int:
    if args.asset.read_bytes()[:4] == b"G2LX":
        print(json.dumps(inspect_file(args.asset), ensure_ascii=False, indent=2))
        return 0
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


def _cmd_export(args: argparse.Namespace) -> int:
    export_file(args.asset, args.output, format=args.format, allow_lossy=args.allow_lossy)
    return 0


def _cmd_convert(args: argparse.Namespace) -> int:
    convert_file(
        args.source,
        args.output,
        input_format=args.input_format,
        output_format=args.format,
        allow_lossy=args.allow_lossy,
    )
    return 0


def _cmd_diff(args: argparse.Namespace) -> int:
    left = open_lexicon(args.left)
    right = open_lexicon(args.right)
    try:
        print(json.dumps(compare(left, right).as_dict(), ensure_ascii=False, indent=2))
    finally:
        left.close()
        right.close()
    return 0


def _cmd_restore(args: argparse.Namespace) -> int:
    if args.asset.read_bytes()[:4] == b"G2LX":
        export_file(args.asset, args.output, format=args.format)
        return 0
    candidate = load(args.asset)
    try:
        entries = {word: candidate.lookup_all(word) for word in candidate}
        write_lexicon(args.output, LexiconData(entries, SourceInfo("restored")), format=args.format)
    finally:
        close = getattr(candidate, "close", None)
        if close is not None:
            close()
    return 0


_MISSING = object()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="g2lex", description="Lossless typed lexicon conversion and reduction."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    pack = sub.add_parser("pack", help="build a deterministic exact G2Lex v1 lexicon")
    pack.add_argument("source", type=Path)
    pack.add_argument("output", type=Path)
    pack.add_argument(
        "--format",
        default="auto",
        choices=(
            "auto",
            "kokoro-json",
            "json-map",
            "tsv",
            "lxc-tsv",
            "jsonl",
            "words",
            "cmudict",
            "mfa",
            "pls",
            "gruut-sqlite",
        ),
    )
    pack.add_argument("--source-id")
    pack.add_argument("--language")
    pack.add_argument("--locale")
    pack.add_argument("--tier")
    pack.add_argument("--provider")
    pack.add_argument("--display-name")
    pack.add_argument("--dialect")
    pack.add_argument("--revision")
    pack.add_argument("--source-url")
    pack.add_argument("--pronunciation-alphabet")
    pack.add_argument("--pronunciation-separator")
    pack.add_argument("--role-namespace")
    pack.add_argument("--license-expression")
    pack.add_argument("--license-name")
    pack.add_argument("--license-url")
    pack.add_argument("--attribution")
    pack.add_argument("--generator")
    pack.add_argument("--parser-id")
    pack.add_argument("--parser-version")
    pack.add_argument("--record-block-entries", type=int, default=256)
    pack.add_argument("--key-block-entries", type=int, default=32)
    pack.add_argument("--compression", choices=("zlib", "none"), default="zlib")
    pack.add_argument("--compression-level", type=int, default=9)
    pack.add_argument("--report", type=Path)
    pack.set_defaults(func=_cmd_pack)

    verify_p = sub.add_parser("verify", help="compare a G2Lex v1 asset with its source")
    verify_p.add_argument("source", type=Path)
    verify_p.add_argument("asset", type=Path)
    verify_p.add_argument(
        "--format",
        default="auto",
        choices=(
            "auto",
            "kokoro-json",
            "json-map",
            "tsv",
            "lxc-tsv",
            "jsonl",
            "words",
            "cmudict",
            "mfa",
            "pls",
            "gruut-sqlite",
        ),
    )
    verify_p.set_defaults(func=_cmd_verify)

    export_p = sub.add_parser("export", help="export a G2Lex v1 asset")
    export_p.add_argument("asset", type=Path)
    export_p.add_argument("output", type=Path)
    export_p.add_argument(
        "--format",
        default="auto",
        choices=("auto", "kokoro-json", "json-map", "tsv", "lxc-tsv", "jsonl", "words"),
    )
    export_p.add_argument("--allow-lossy", action="store_true")
    export_p.set_defaults(func=_cmd_export)

    convert_p = sub.add_parser("convert", help="convert between source formats")
    convert_p.add_argument("source", type=Path)
    convert_p.add_argument("output", type=Path)
    convert_p.add_argument(
        "--input-format",
        default="auto",
        choices=(
            "auto",
            "json",
            "tsv",
            "lxc-tsv",
            "jsonl",
            "words",
            "cmudict",
            "mfa",
            "pls",
            "gruut-sqlite",
        ),
    )
    convert_p.add_argument(
        "--format", default="auto", choices=("auto", "json", "tsv", "lxc-tsv", "jsonl", "words")
    )
    convert_p.add_argument("--allow-lossy", action="store_true")
    convert_p.set_defaults(func=_cmd_convert)

    lookup_p = sub.add_parser("lookup", help="look up one G2Lex v1 spelling")
    lookup_p.add_argument("asset", type=Path)
    lookup_p.add_argument("word")
    lookup_p.set_defaults(func=_cmd_lookup)

    inspect_p = sub.add_parser("inspect", help="show asset metadata and metrics")
    inspect_p.add_argument("asset", type=Path)
    inspect_p.set_defaults(func=_cmd_inspect)

    restore_p = sub.add_parser("restore", help="materialize an asset into a source format")
    restore_p.add_argument("asset", type=Path)
    restore_p.add_argument("output", type=Path)
    restore_p.add_argument(
        "--format", default="auto", choices=("auto", "json", "tsv", "lxc-tsv", "jsonl", "words")
    )
    restore_p.set_defaults(func=_cmd_restore)
    diff_p = sub.add_parser("diff", help="compare two G2Lex v1 assets")
    diff_p.add_argument("left", type=Path)
    diff_p.add_argument("right", type=Path)
    diff_p.set_defaults(func=_cmd_diff)

    reduce_p = sub.add_parser("reduce", help="experimental resident-entry reduction")
    reduce_p.add_argument("source", type=Path)
    reduce_p.add_argument("output", type=Path)
    reduce_p.add_argument("--format", choices=("auto", "json", "tsv"), default="auto")
    reduce_p.add_argument(
        "--profile",
        choices=("generic", "de-compound", "de-boundary", "de-linkers"),
        default="generic",
    )
    reduce_p.add_argument("--max-components", type=int, default=4)
    reduce_p.add_argument("--max-states", type=int, default=100_000)
    reduce_p.add_argument("--target-literals", type=int, default=400_000)
    reduce_p.add_argument("--optimizer", choices=("greedy", "utility"), default="greedy")
    reduce_p.add_argument("--max-passes", type=int, default=4)
    reduce_p.add_argument("--recursive-components", action="store_true")
    reduce_p.add_argument("--max-recursive-depth", type=int, default=4)
    reduce_p.add_argument("--segmentation-scorer", choices=("v1", "v2"), default="v1")
    reduce_p.add_argument("--report", type=Path)
    reduce_p.set_defaults(func=_cmd_reduce)

    experimental = sub.add_parser("experimental", help="experimental reduction tools")
    experimental_sub = experimental.add_subparsers(dest="experimental_command", required=True)
    verify_reduced = experimental_sub.add_parser(
        "verify-reduced", help="verify an experimental reduction asset against its source"
    )
    verify_reduced.add_argument("source", type=Path)
    verify_reduced.add_argument("asset", type=Path)
    verify_reduced.add_argument("--format", choices=("auto", "json", "tsv"), default="auto")
    verify_reduced.set_defaults(func=_cmd_verify_reduced)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
