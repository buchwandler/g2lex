"""Montreal Forced Aligner plain pronunciation dictionary adapter."""

from __future__ import annotations

from pathlib import Path

from ..model import TypedLexiconData
from .common import result

_PROBABILISTIC_ERROR = "probabilistic MFA dictionaries are not supported by g2lex format v1"


def parse_mfa_bytes(
    data: bytes,
    *,
    path: Path | None = None,
    source_id: str | None = None,
    comment_policy: str = "skip",
) -> TypedLexiconData:
    """Parse plain ``WORD<TAB>PHONE PHONE`` MFA dictionaries.

    MFA rows with additional tab-separated fields are rejected because they carry
    probabilities or other fields that schema 1 cannot preserve.
    """
    if comment_policy not in {"skip", "error"}:
        raise ValueError("comment_policy must be 'skip' or 'error'")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("MFA input is not valid UTF-8") from exc

    entries: dict[str, list[str]] = {}
    physical_rows = 0
    for line_number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("#", ";")):
            if comment_policy == "error":
                raise ValueError(f"MFA:{line_number}: comments are not allowed")
            continue
        fields = line.rstrip("\r\n").split("\t")
        if len(fields) > 2:
            raise ValueError(_PROBABILISTIC_ERROR)
        if len(fields) != 2 or not fields[0].strip() or not fields[1].strip():
            raise ValueError(f"MFA:{line_number}: expected WORD<TAB>PHONE PHONE")
        word = fields[0].strip()
        pronunciation = fields[1].strip()
        entries.setdefault(word, []).append(pronunciation)
        physical_rows += 1
    return result(
        {word: tuple(values) for word, values in entries.items()},
        path=path,
        data=data,
        fmt="mfa",
        source_id=source_id,
        physical_rows=physical_rows,
    )
