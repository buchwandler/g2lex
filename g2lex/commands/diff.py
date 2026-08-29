"""The ``diff`` command."""

from __future__ import annotations

import json
from argparse import Namespace

from ..lexicon import open_lexicon
from ..verify_exact import compare


def _cmd_diff(args: Namespace) -> int:
    left = open_lexicon(args.left)
    right = open_lexicon(args.right)
    try:
        print(json.dumps(compare(left, right).as_dict(), ensure_ascii=False, indent=2))
    finally:
        left.close()
        right.close()
    return 0
