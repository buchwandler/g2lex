"""Recursive anti-cheating checks for the complete runtime representation."""
from __future__ import annotations

import json
from dataclasses import fields
from typing import Any

from .model import ImplicitLexicon

_FORBIDDEN_NAMES = {
    "derived", "generated", "generated_words", "recipes", "recipe_by_word", "word_ids",
    "rule_by_word", "split_by_word", "components_by_word", "selector_by_word", "repair_by_word",
    "linker_by_word", "generated_ids", "exceptions_by_word", "candidate_by_word", "model_by_word",
}
_FORBIDDEN_PATTERNS = ("word_to_", "_by_word", "per_word_", "exceptions_by_word", "stage_by_word", "model_by_word", "candidate_by_word")


def _forbidden_name(value: object) -> bool:
    name = str(value).lower()
    return name in _FORBIDDEN_NAMES or any(pattern in name for pattern in _FORBIDDEN_PATTERNS)


def _audit_value(value: Any, path: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if _forbidden_name(key):
                findings.append(f"{path}.{key}")
            findings.extend(_audit_value(child, f"{path}.{key}"))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            findings.extend(_audit_value(child, f"{path}[{index}]"))
    return findings


def _serializable(value: Any) -> Any:
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if isinstance(value, dict):
        return {str(key): _serializable(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serializable(child) for child in value]
    return value


def audit_runtime_representation(candidate: ImplicitLexicon) -> dict[str, Any]:
    """Reject per-word runtime data and return model/structure accounting."""
    forbidden_fields = sorted(field.name for field in fields(candidate) if _forbidden_name(field.name))
    if forbidden_fields:
        raise AssertionError(f"forbidden runtime fields: {forbidden_fields}")
    inspected = {
        "metadata": candidate.metadata,
        "composer": candidate.composer.rules.as_dict(),
        "runtime_program": _serializable(candidate.runtime_program),
        "membership": {"backend_id": getattr(candidate.membership, "backend_id", "unknown")},
        "literals": {"backend_id": getattr(candidate.literals, "backend_id", "unknown")},
    }
    findings = _audit_value(inspected, "runtime")
    if findings:
        raise AssertionError(f"forbidden serialized runtime structures: {findings}")
    selector = getattr(candidate.runtime_program, "selector", None)
    if selector is None:
        selector = getattr(candidate.composer.rules, "selector", None)
    max_bytes = getattr(selector, "max_serialized_bytes", None)
    if max_bytes is not None and getattr(selector, "serialized_bytes", 0) > max_bytes:
        raise AssertionError("selector exceeds declared serialized byte limit")
    if candidate.per_generated_word_recipe_count != 0:
        raise AssertionError("generated words have runtime recipes")
    runtime_dict = _serializable(candidate.runtime_program)
    model_bytes = len(json.dumps(runtime_dict, sort_keys=True, separators=(",", ":")).encode())
    return {
        "forbidden_fields": [],
        "forbidden_metadata": [],
        "literal_word_count": candidate.literal_word_count,
        "per_generated_word_recipe_count": candidate.per_generated_word_recipe_count,
        "runtime_model_bytes": model_bytes,
        "checked": True,
    }


__all__ = ["audit_runtime_representation"]
