"""Named adapters for exact typed lexicon sources."""

from .cmudict import parse_cmudict_bytes
from .gruut_sqlite import parse_gruut_sqlite
from .json_map import parse_json_map_bytes
from .jsonl import parse_jsonl_bytes
from .kokoro_json import parse_kokoro_json_bytes
from .mfa import parse_mfa_bytes
from .pls import parse_pls_bytes
from .tsv import parse_extended_tsv_bytes, parse_tsv_bytes
from .words import parse_word_list_bytes

__all__ = [
    "parse_cmudict_bytes",
    "parse_extended_tsv_bytes",
    "parse_gruut_sqlite",
    "parse_json_map_bytes",
    "parse_jsonl_bytes",
    "parse_kokoro_json_bytes",
    "parse_mfa_bytes",
    "parse_pls_bytes",
    "parse_tsv_bytes",
    "parse_word_list_bytes",
]
