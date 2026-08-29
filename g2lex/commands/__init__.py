"""Command handlers for the :mod:`g2lex.cli` entry point."""

from .convert import _cmd_convert
from .diff import _cmd_diff
from .export import _cmd_export
from .inspect import _cmd_inspect
from .lookup import _cmd_lookup
from .pack import _cmd_pack
from .reduce import _cmd_reduce
from .restore import _cmd_restore
from .verify import _cmd_verify, _cmd_verify_reduced

__all__ = [
    "_cmd_convert",
    "_cmd_diff",
    "_cmd_export",
    "_cmd_inspect",
    "_cmd_lookup",
    "_cmd_pack",
    "_cmd_reduce",
    "_cmd_restore",
    "_cmd_verify",
    "_cmd_verify_reduced",
]
