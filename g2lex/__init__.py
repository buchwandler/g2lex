"""G2Lex compiled pronunciation lexicons for Python."""

from __future__ import annotations

from ._version import __version__
from .io import LexiconFormatError, parse_typed_bytes, read_typed_lexicon
from .layers import CaseAliasMapping, LayeredLexicon, LayerHit, LexiconLayer
from .lexicon import Lexicon, LexiconRecord, open, open_bytes, open_traversable
from .model import SourceInfo, TypedLexiconData
from .operations import export_file, inspect_file, pack_file, verify_file
from .value import (
    WORD_ONLY,
    LexiconValue,
    TaggedValue,
    first_pronunciation,
    logical_sha256,
    pronunciation_variants,
)
from .verify_exact import compare

__all__ = [
    "WORD_ONLY",
    "CaseAliasMapping",
    "LayerHit",
    "LayeredLexicon",
    "Lexicon",
    "LexiconFormatError",
    "LexiconLayer",
    "LexiconRecord",
    "LexiconValue",
    "SourceInfo",
    "TaggedValue",
    "TypedLexiconData",
    "__version__",
    "compare",
    "export_file",
    "first_pronunciation",
    "inspect_file",
    "logical_sha256",
    "open",
    "open_bytes",
    "open_traversable",
    "pack_file",
    "parse_typed_bytes",
    "pronunciation_variants",
    "read_typed_lexicon",
    "verify_file",
]
