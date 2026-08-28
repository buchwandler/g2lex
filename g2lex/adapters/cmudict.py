"""CMU Pronouncing Dictionary source adapter."""

from __future__ import annotations

import re
from pathlib import Path

from ..model import TypedLexiconData
from .common import result

_VARIANT = re.compile(r"^(?P<word>.+)\((?P<number>\d+)\)$")


def parse_cmudict_bytes(
    data: bytes,
    *,
    path: Path | None = None,
    source_id: str | None = None,
    comment_policy: str = "skip",
) -> TypedLexiconData:
    """Parse CMUdict rows, grouping numbered pronunciations by their base word."""
    if comment_policy not in {"skip", "error"}:
        raise ValueError("comment_policy must be 'skip' or 'error'")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("CMUdict input is not valid UTF-8") from exc

    entries: dict[str, list[str]] = {}
    physical_rows = 0
    for line_number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith((";;;", "#")):
            if comment_policy == "error":
                raise ValueError(f"CMUdict:{line_number}: comments are not allowed")
            continue
        fields = stripped.split(None, 1)
        if len(fields) != 2 or not fields[0] or not fields[1].strip():
            raise ValueError(f"CMUdict:{line_number}: expected WORD and pronunciation")
        match = _VARIANT.fullmatch(fields[0])
        word = match.group("word") if match else fields[0]
        pronunciation = fields[1].strip()
        entries.setdefault(word, []).append(pronunciation)
        physical_rows += 1
    return result(
        {word: tuple(values) for word, values in entries.items()},
        path=path,
        data=data,
        fmt="cmudict",
        source_id=source_id,
        physical_rows=physical_rows,
    )
