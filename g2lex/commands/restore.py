"""The ``restore`` command."""

from __future__ import annotations

from argparse import Namespace

from ..asset import load
from ..io import LexiconData, write_lexicon
from ..model import SourceInfo
from ..operations import export_file


def _cmd_restore(args: Namespace) -> int:
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
