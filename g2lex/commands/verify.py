"""Stable and experimental verification commands."""

from __future__ import annotations

import json
from argparse import Namespace

from ..asset import load
from ..io import read_lexicon
from ..operations import verify_file
from ..verify import verify_candidate


def _cmd_verify(args: Namespace) -> int:
    if args.asset.read_bytes()[:4] != b"G2LX":
        raise ValueError(
            "verify accepts G2Lex v1 assets; use 'experimental verify-reduced' for reduction assets"
        )
    result = verify_file(args.source, args.asset, input_format=args.format)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["lossless"] else 1


def _cmd_verify_reduced(args: Namespace) -> int:
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
