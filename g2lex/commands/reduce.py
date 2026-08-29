"""Experimental reduction command."""

from __future__ import annotations

import json
from argparse import Namespace

from ..asset import runtime_asset_bytes, save
from ..io import read_lexicon
from ..reduce import ReductionConfig, reduce_lexicon
from ..reports import summary_dict
from ..segmentation import SegmentationScorer
from ..verify import verify_candidate
from .common import profile


def _cmd_reduce(args: Namespace) -> int:
    source = read_lexicon(args.source, format=args.format)
    rules, linkers = profile(args.profile)
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
