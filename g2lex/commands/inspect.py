"""The ``inspect`` command."""

from __future__ import annotations

import json
from argparse import Namespace
from dataclasses import asdict

from ..asset import load, runtime_asset_bytes
from ..model import ImplicitLexicon
from ..operations import inspect_file


def _cmd_inspect(args: Namespace) -> int:
    if args.asset.read_bytes()[:4] == b"G2LX":
        print(json.dumps(inspect_file(args.asset), ensure_ascii=False, indent=2))
        return 0
    candidate = load(args.asset)
    assert isinstance(candidate, ImplicitLexicon)
    summary = {
        **asdict(candidate.metrics()),
        "membership_state_count": getattr(candidate.membership, "state_count", 0),
        "membership_edge_count": getattr(candidate.membership, "edge_count", 0),
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
