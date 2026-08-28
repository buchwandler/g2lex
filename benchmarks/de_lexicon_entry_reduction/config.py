"""TOML configuration resolution for reproducible V4 experiments."""
from __future__ import annotations

import hashlib
import json
try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "source": {"id": "builtin", "path": None, "data_root": None},
    "seed": 0,
    "limits": {"max_states": 100_000, "target_literals": 400_000, "max_components": 4, "max_recursive_depth": 4},
    "storage": {"membership_backend": "dafsa-json-v1", "literal_backend": "dict-json-v3", "pronunciation_codec": "utf8", "asset_format": "v3"},
    "verification": {"required": True, "adversarial_misses": True},
    "runtime": {"sample_size": 1000, "fresh_process": True},
    "output": "runs",
    "cases": [],
}


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


@dataclass(frozen=True, slots=True)
class ResolvedConfig:
    path: str
    values: dict[str, Any]
    sha256: str

    def as_dict(self) -> dict[str, Any]:
        return self.values

    def write(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.values, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def resolve_config(value: dict[str, Any], *, path: str = "<memory>") -> ResolvedConfig:
    merged = _merge(DEFAULTS, value)
    cases = merged.get("cases", [])
    if isinstance(cases, dict):
        cases = [{"name": name, **case} for name, case in sorted(cases.items())]
    normalized_cases = []
    for index, case in enumerate(cases):
        item = dict(case)
        item.setdefault("name", f"case-{index + 1:03d}")
        item.setdefault("mode", "implicit-compound")
        item.setdefault("optimizer", "greedy")
        item.setdefault("selector", "v1")
        item.setdefault("boundary_rules", "v1")
        item.setdefault("linkers", "v1")
        item.setdefault("segmentation_scorer", "v1")
        normalized_cases.append(item)
    merged["cases"] = normalized_cases
    payload = json.dumps(merged, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return ResolvedConfig(path, merged, hashlib.sha256(payload).hexdigest())


def load_config(path: str | Path) -> ResolvedConfig:
    source = Path(path)
    with source.open("rb") as handle:
        value = tomllib.load(handle)
    if not isinstance(value, dict):
        raise ValueError("configuration root must be a TOML table")
    return resolve_config(value, path=str(source))


__all__ = ["DEFAULTS", "ResolvedConfig", "load_config", "resolve_config"]
