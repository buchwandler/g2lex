"""The ``convert`` command."""

from __future__ import annotations

from argparse import Namespace

from ..operations import convert_file


def _cmd_convert(args: Namespace) -> int:
    convert_file(
        args.source,
        args.output,
        input_format=args.input_format,
        output_format=args.format,
        allow_lossy=args.allow_lossy,
    )
    return 0
