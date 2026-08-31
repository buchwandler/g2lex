"""The stable ``lookup`` command."""

from __future__ import annotations

import json
from argparse import Namespace

from ..asset import load
from ..lexicon import open_lexicon
from .common import MISSING, plain_lookup


def _cmd_lookup(args: Namespace) -> int:
    if args.asset.read_bytes()[:4] != b"G2LX":
        candidate = load(args.asset)
        values = candidate.lookup_all(args.word)
        if not values:
            return 1
        for pronunciation in values:
            print(pronunciation)
        return 0
    candidate = open_lexicon(args.asset)
    try:
        lookup_value = candidate.get(args.word, MISSING)
        if lookup_value is MISSING:
            return 1
        print(json.dumps(plain_lookup(lookup_value), ensure_ascii=False))
        return 0
    finally:
        candidate.close()
