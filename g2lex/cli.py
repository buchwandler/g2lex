"""Command-line interface for g2lex."""

from __future__ import annotations

import argparse
from pathlib import Path

from .commands import (
    _cmd_convert,
    _cmd_diff,
    _cmd_export,
    _cmd_inspect,
    _cmd_lookup,
    _cmd_pack,
    _cmd_reduce,
    _cmd_restore,
    _cmd_verify,
    _cmd_verify_reduced,
)

try:
    from ._version import __version__
except ImportError:
    __version__ = "0+unknown"


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
            "ipa-tsv",
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
            "ipa-tsv",
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
            "ipa-tsv",
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
