"""The ``export`` command."""

from __future__ import annotations

from argparse import Namespace

from ..operations import export_file


def _cmd_export(args: Namespace) -> int:
    export_file(args.asset, args.output, format=args.format, allow_lossy=args.allow_lossy)
    return 0
