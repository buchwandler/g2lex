"""Strict TOML configuration resolution for reproducible experiments."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

from lexcompact.backends import CODECS, LITERAL_BACKENDS, MEMBERSHIP_BACKENDS

SCHEMA_VERSION = 1
DEFAULTS: dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "source": {"id": "builtin", "path": None, "data_root": None},
    "source_lock": None,
    "seed": 0,
    "limits": {
        "max_states": 100_000,
        "target_literals": 400_000,
        "max_components": 4,
        "max_recursive_depth": 4,
    },
    "storage": {
        "membership_backend": "dafsa-json-v1",
        "literal_backend": "dict-json-v3",
        "pronunciation_codec": "utf8",
        "asset_format": "v3",
    },
    "verification": {"required": True, "adversarial_misses": True},
    "runtime": {
        "sample_size": 1000,
        "fresh_process": True,
        "repetitions": 3,
        "finalist_repetitions": 7,
    },
    "output": "runs",
    "cases": [],
    "methods": {},
}

_ROOT_KEYS = set(DEFAULTS) | {"strict", "expected_baseline_word_count", "release_mode"}
_SOURCE_KEYS = {"id", "path", "data_root"}
_LIMIT_KEYS = {"max_states", "target_literals", "max_components", "max_recursive_depth"}
_STORAGE_KEYS = {"membership_backend", "literal_backend", "pronunciation_codec", "asset_format"}
_VERIFICATION_KEYS = {"required", "adversarial_misses"}
_RUNTIME_KEYS = {"sample_size", "fresh_process", "repetitions", "finalist_repetitions"}
_METHOD_KEYS = {"compound", "morphology", "rewrite", "cart", "graphone", "neural", "selector"}
_METHOD_OPTION_KEYS = {
    "enabled",
    "boundary_rules",
    "linkers",
    "recursive_components",
    "segmentation_scorer",
    "max_rules",
    "min_support",
    "max_bytes",
    "max_output_chunk_length",
    "order",
    "max_graphemes_per_unit",
    "implementation",
    "kind",
    "max_serialized_bytes",
}
_CASE_KEYS = {
    "name",
    "inherits",
    "source",
    "source_lock",
    "data_root",
    "path",
    "target_literals",
    "max_components",
    "max_states",
    "optimizer",
    "selector",
    "boundary_rules",
    "linkers",
    "recursive_components",
    "max_recursive_depth",
    "segmentation_scorer",
    "asset_format",
    "membership_backend",
    "literal_backend",
    "pronunciation_codec",
    "methods",
    "storage",
    "runtime",
    "verification",
    "mode",
    "max_passes",
    "strict",
}


@dataclass(frozen=True, slots=True)
class ResolvedConfig:
    path: str
    values: dict[str, Any]
    sha256: str

    def as_dict(self) -> dict[str, Any]:
        return self.values

    def write(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.values, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _check_keys(value: dict[str, Any], allowed: set[str], where: str, strict: bool) -> None:
    if strict:
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(f"unknown {where} key(s): {', '.join(unknown)}")


def _validate_methods(methods: Any, where: str, strict: bool) -> dict[str, Any]:
    if methods is None:
        return {}
    if not isinstance(methods, dict):
        raise TypeError(f"{where} must be a TOML table")
    _check_keys(methods, _METHOD_KEYS, where, strict)
    for name, value in methods.items():
        if name == "selector" and isinstance(value, str):
            if value not in {
                "static-priority",
                "priority",
                "rule-tree",
                "hashed-logistic",
                "forest",
                "gbdt",
            }:
                raise ValueError(f"unknown selector method: {value}")
            continue
        if not isinstance(value, dict):
            raise TypeError(f"{where}.{name} must be a TOML table")
        _check_keys(value, _METHOD_OPTION_KEYS, f"{where}.{name}", strict)
        if "enabled" in value and not isinstance(value["enabled"], bool):
            raise ValueError(f"{where}.{name}.enabled must be boolean")
    return methods


def _validate_storage(storage: dict[str, Any], where: str) -> None:
    for key in ("membership_backend", "literal_backend", "pronunciation_codec"):
        if key in storage:
            values = {
                "membership_backend": MEMBERSHIP_BACKENDS,
                "literal_backend": LITERAL_BACKENDS,
                "pronunciation_codec": CODECS,
            }[key]
            if storage[key] not in values:
                raise ValueError(f"unknown {key}: {storage[key]}")
    if storage.get("asset_format", "v3") not in {"v3", "v4"}:
        raise ValueError(f"unknown asset format: {storage.get('asset_format')}")


def _normal_case(case: dict[str, Any], index: int, strict: bool) -> dict[str, Any]:
    item = dict(case)
    _check_keys(item, _CASE_KEYS, f"case {index + 1}", strict)
    item.setdefault("name", f"case-{index + 1:03d}")
    item.setdefault("mode", "implicit-compound")
    item.setdefault("optimizer", "greedy")
    item.setdefault("selector", "v1")
    item.setdefault("boundary_rules", "v1")
    item.setdefault("linkers", "v1")
    item.setdefault("segmentation_scorer", "v1")
    if "storage" in item:
        if not isinstance(item["storage"], dict):
            raise ValueError(f"case {item['name']}.storage must be a TOML table")
        _check_keys(item["storage"], _STORAGE_KEYS, f"case {item['name']}.storage", strict)
        _validate_storage(item["storage"], f"case {item['name']}.storage")
    if "methods" in item:
        _validate_methods(item["methods"], f"case {item['name']}.methods", strict)
    if "runtime" in item:
        _check_keys(item["runtime"], _RUNTIME_KEYS, f"case {item['name']}.runtime", strict)
    return item


def _expand_cases(raw: Any, strict: bool) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        values = [{"name": name, **value} for name, value in sorted(raw.items())]
    elif isinstance(raw, list):
        values = raw
    else:
        raise TypeError("cases must be a TOML array of tables or named table")
    by_name = {
        str(item.get("name", f"case-{index + 1:03d}")): _normal_case(item, index, strict)
        for index, item in enumerate(values)
    }
    resolving: set[str] = set()

    def resolve(name: str) -> dict[str, Any]:
        if name in resolving:
            raise ValueError(f"case inheritance cycle at {name}")
        item = by_name[name]
        parent = item.get("inherits")
        if not parent:
            return _merge({}, item)
        parent_names = [parent] if isinstance(parent, str) else parent
        if not isinstance(parent_names, list) or not all(
            str(value) in by_name for value in parent_names
        ):
            raise ValueError(f"case {name} inherits an unknown case")
        resolving.add(name)
        result: dict[str, Any] = {}
        for parent_name in parent_names:
            result = _merge(result, resolve(str(parent_name)))
        resolving.remove(name)
        return _merge(result, item)

    return [resolve(name) for name in by_name]


def resolve_config(value: dict[str, Any], *, path: str = "<memory>") -> ResolvedConfig:
    if not isinstance(value, dict):
        raise TypeError("configuration root must be a TOML table")
    strict = bool(value.get("strict", True))
    _check_keys(value, _ROOT_KEYS, "configuration", strict)
    schema_version = int(value.get("schema_version", SCHEMA_VERSION))
    if schema_version != SCHEMA_VERSION:
        raise ValueError(f"unsupported configuration schema_version: {schema_version}")
    merged = _merge(DEFAULTS, value)
    for name, allowed in (
        ("source", _SOURCE_KEYS),
        ("limits", _LIMIT_KEYS),
        ("storage", _STORAGE_KEYS),
        ("verification", _VERIFICATION_KEYS),
        ("runtime", _RUNTIME_KEYS),
    ):
        section = merged.get(name)
        if not isinstance(section, dict):
            raise TypeError(f"{name} must be a TOML table")
        _check_keys(section, allowed, name, strict)
    _validate_storage(merged["storage"], "storage")
    _validate_methods(merged.get("methods", {}), "methods", strict)
    cases = _expand_cases(merged.get("cases", []), strict)
    if not cases:
        raise ValueError("configuration must define at least one case")
    merged["cases"] = []
    full_source = bool(
        merged.get("release_mode", False)
        or int(merged.get("expected_baseline_word_count", 0)) >= 738427
    )
    if full_source and not merged.get("source_lock"):
        raise ValueError("full-source configuration requires source_lock")
    for case in cases:
        case_storage = dict(case.get("storage", {}))
        for key in ("membership_backend", "literal_backend", "pronunciation_codec", "asset_format"):
            if key in case:
                case_storage[key] = case[key]
        effective = _merge(merged["storage"], case_storage)
        _validate_storage(effective, f"case {case['name']} storage")
        runtime = _merge(merged["runtime"], case.get("runtime", {}))
        if int(runtime["sample_size"]) < 1 or int(runtime["repetitions"]) < 1:
            raise ValueError(
                f"case {case['name']} runtime sample_size and repetitions must be positive"
            )
        if case.get("max_components", merged["limits"]["max_components"]) < 1:
            raise ValueError(f"case {case['name']} max_components must be positive")
        case["storage"] = effective
        case["runtime"] = runtime
        case["effective_config_sha256"] = hashlib.sha256(
            json.dumps(case, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        merged["cases"].append(case)
    payload = json.dumps(merged, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return ResolvedConfig(path, merged, hashlib.sha256(payload).hexdigest())


def load_config(path: str | Path) -> ResolvedConfig:
    source = Path(path)
    with source.open("rb") as handle:
        value = tomllib.load(handle)
    return resolve_config(value, path=str(source))


__all__ = ["DEFAULTS", "ResolvedConfig", "load_config", "resolve_config"]
