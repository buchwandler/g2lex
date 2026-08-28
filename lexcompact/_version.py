"""Small dependency-free Git-derived version helper used by setuptools."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

_FALLBACK = "0.3.0.dev0"
_TAG = re.compile(
    r"^v?(?P<base>\d+\.\d+\.\d+)(?:-(?P<count>\d+)-g(?P<sha>[0-9a-f]+))?(?P<dirty>-dirty)?$"
)


def get_version() -> str:
    override = os.environ.get("LEXCOMPACT_VERSION")
    if override:
        return override
    root = Path(__file__).resolve().parents[1]
    try:
        text = subprocess.check_output(
            [
                "git",
                "-C",
                str(root),
                "describe",
                "--tags",
                "--long",
                "--dirty",
                "--match",
                "v[0-9]*",
            ],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return _FALLBACK
    match = _TAG.match(text)
    if not match:
        return _FALLBACK
    base = match.group("base")
    count = int(match.group("count") or 0)
    sha = match.group("sha")
    dirty = bool(match.group("dirty"))
    if count == 0 and not dirty:
        return base
    local = []
    if sha:
        local.append(f"g{sha}")
    if dirty:
        local.append("dirty")
    version = f"{base}.post{count}" if count else f"{base}.dev0"
    return version + ("+" + ".".join(local) if local else "")


__version__ = get_version()
