"""Bounded shared reconstruction stages for morphology and rewrites."""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from .model import PronunciationTuple
from .runtime import ReconstructionCandidate


def _resolve(context: Any, spelling: str) -> PronunciationTuple | None:
    resolver = getattr(context, "resolve", None)
    if resolver is not None:
        return resolver(spelling)
    if isinstance(context, Mapping):
        value = context.get(spelling)
        return tuple(value) if value is not None else None
    return None


@dataclass(frozen=True, slots=True)
class AffixRule:
    rule_id: int
    spelling_prefix: str = ""
    spelling_suffix: str = ""
    strip_prefix: str = ""
    strip_suffix: str = ""
    required_left_context: str = ""
    required_right_context: str = ""
    pronunciation_prefix_add: str = ""
    pronunciation_suffix_add: str = ""
    pronunciation_prefix_remove: str = ""
    pronunciation_suffix_remove: str = ""
    capitalization_class: str | None = None
    min_stem_length: int = 1

    def as_dict(self) -> dict[str, object]:
        return {"rule_id": self.rule_id, **{name: getattr(self, name) for name in self.__dataclass_fields__ if name != "rule_id"}}

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "AffixRule":
        return cls(**{name: value[name] for name in cls.__dataclass_fields__ if name in value})

    def apply(self, word: str, context: Any) -> tuple[ReconstructionCandidate, ...]:
        if self.spelling_prefix and not word.startswith(self.spelling_prefix):
            return ()
        if self.spelling_suffix and not word.endswith(self.spelling_suffix):
            return ()
        stem_start = len(self.strip_prefix)
        stem_end = len(word) - len(self.strip_suffix) if self.strip_suffix else len(word)
        if self.strip_prefix and not word.startswith(self.strip_prefix):
            return ()
        if self.strip_suffix and not word.endswith(self.strip_suffix):
            return ()
        stem = word[stem_start:stem_end]
        if len(stem) < self.min_stem_length or len(stem) >= len(word):
            return ()
        if self.required_left_context and not stem.startswith(self.required_left_context):
            return ()
        if self.required_right_context and not stem.endswith(self.required_right_context):
            return ()
        if self.capitalization_class and _capitalization(word) != self.capitalization_class:
            return ()
        values = _resolve(context, stem)
        if values is None:
            return ()
        transformed = tuple(self._transform(value) for value in values)
        return (ReconstructionCandidate("morphology", transformed, str(self.rule_id), component_count=1, analysis_kind="affix"),)

    def _transform(self, pronunciation: str) -> str:
        value = pronunciation
        if self.pronunciation_prefix_remove and value.startswith(self.pronunciation_prefix_remove):
            value = value[len(self.pronunciation_prefix_remove) :]
        if self.pronunciation_suffix_remove and value.endswith(self.pronunciation_suffix_remove):
            value = value[: -len(self.pronunciation_suffix_remove)]
        return self.pronunciation_prefix_add + value + self.pronunciation_suffix_add


class MorphologyReconstructor:
    stage_id = "morphology"
    version = "1"

    def __init__(self, rules: Iterable[AffixRule], *, max_rules: int = 4096) -> None:
        self.rules = tuple(sorted(rules, key=lambda rule: rule.rule_id))[:max_rules]

    def candidates(self, word: str, context: Any) -> tuple[ReconstructionCandidate, ...]:
        return tuple(candidate for rule in self.rules for candidate in rule.apply(word, context))

    def as_dict(self) -> Mapping[str, object]:
        return {"stage_id": self.stage_id, "version": self.version, "rules": [rule.as_dict() for rule in self.rules]}

    def serialize_sections(self) -> Mapping[str, bytes]:
        return {"reconstructor.morphology": json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":")).encode()}


def _capitalization(word: str) -> str:
    if word.isupper():
        return "upper"
    if word[:1].isupper():
        return "initial-upper"
    if word.islower():
        return "lower"
    return "mixed"


def mine_morphology(
    entries: Mapping[str, PronunciationTuple],
    *,
    min_support: int = 2,
    max_rules: int = 4096,
) -> tuple[AffixRule, ...]:
    """Mine bounded suffix and prefix transforms from exact source pairs."""
    observations: Counter[tuple[str, str, str, str]] = Counter()
    for word, values in entries.items():
        for stem, stem_values in entries.items():
            if len(stem) >= len(word):
                continue
            if word.startswith(stem):
                spelling_suffix = word[len(stem) :]
                if spelling_suffix and values and stem_values:
                    observations[("suffix", spelling_suffix, stem_values[0], values[0])] += 1
            if word.endswith(stem):
                spelling_prefix = word[: -len(stem)]
                if spelling_prefix and values and stem_values:
                    observations[("prefix", spelling_prefix, stem_values[0], values[0])] += 1
    rules: list[AffixRule] = []
    for index, (kind, affix, stem_pronunciation, word_pronunciation) in enumerate(sorted(observations)):
        if observations[(kind, affix, stem_pronunciation, word_pronunciation)] < min_support:
            continue
        if kind == "suffix":
            added = word_pronunciation[len(stem_pronunciation) :] if word_pronunciation.startswith(stem_pronunciation) else ""
            rules.append(AffixRule(index, spelling_suffix=affix, strip_suffix=affix, pronunciation_suffix_add=added))
        else:
            added = word_pronunciation[: -len(stem_pronunciation)] if word_pronunciation.endswith(stem_pronunciation) else ""
            rules.append(AffixRule(index, spelling_prefix=affix, strip_prefix=affix, pronunciation_prefix_add=added))
        if len(rules) >= max_rules:
            break
    return tuple(rules)


@dataclass(frozen=True, slots=True)
class RewriteRule:
    rule_id: int
    operation: str
    spelling_left: str = ""
    spelling_right: str = ""
    pronunciation_left: str = ""
    pronunciation_right: str = ""
    pattern: str = ""
    replacement: str = ""
    source_stage: str | None = None
    boundary_class: str | None = None
    capitalization_class: str | None = None
    word_length_bucket: int | None = None
    support: int = 0
    conflicts: int = 0
    serialized_bytes: int = 0
    net_bytes_saved: int = 0

    def as_dict(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "RewriteRule":
        return cls(**{name: value[name] for name in cls.__dataclass_fields__ if name in value})

    def applies(self, word: str, pronunciation: str, stage_id: str | None = None) -> bool:
        if self.source_stage is not None and self.source_stage != stage_id:
            return False
        if self.spelling_left and self.spelling_left not in word:
            return False
        if self.spelling_right and self.spelling_right not in word:
            return False
        if self.pronunciation_left and self.pronunciation_left not in pronunciation:
            return False
        if self.pronunciation_right and self.pronunciation_right not in pronunciation:
            return False
        return bool(self.pattern) and self.pattern in pronunciation

    def apply(self, word: str, pronunciation: str, stage_id: str | None = None) -> str | None:
        if not self.applies(word, pronunciation, stage_id):
            return None
        if self.operation == "insert":
            return pronunciation.replace(self.pattern, self.pattern + self.replacement, 1)
        if self.operation == "delete":
            return pronunciation.replace(self.pattern, "", 1)
        if self.operation == "replace":
            return pronunciation.replace(self.pattern, self.replacement, 1)
        raise ValueError(f"unknown rewrite operation: {self.operation!r}")


class RewriteReconstructor:
    stage_id = "rewrite"
    version = "1"

    def __init__(self, rules: Iterable[RewriteRule], *, max_rules: int = 4096) -> None:
        self.rules = tuple(sorted(rules, key=lambda rule: rule.rule_id))[:max_rules]

    def candidates(self, word: str, context: Any) -> tuple[ReconstructionCandidate, ...]:
        base = context.get("candidates", ()) if isinstance(context, Mapping) else getattr(context, "candidates", ())
        result: list[ReconstructionCandidate] = []
        for candidate in base:
            pronunciation = candidate.pronunciation[0] if candidate.pronunciation else ""
            for rule in self.rules:
                rewritten = rule.apply(word, pronunciation, candidate.stage_id)
                if rewritten is not None:
                    result.append(ReconstructionCandidate(self.stage_id, (rewritten,), str(rule.rule_id), analysis_kind="rewrite"))
        return tuple(result)

    def as_dict(self) -> Mapping[str, object]:
        return {"stage_id": self.stage_id, "version": self.version, "rules": [rule.as_dict() for rule in self.rules]}

    def serialize_sections(self) -> Mapping[str, bytes]:
        return {"reconstructor.rewrite": json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":")).encode()}


def induce_rewrite_rules(observations: Iterable[Mapping[str, object]], *, max_rules: int = 4096) -> tuple[RewriteRule, ...]:
    """Create shared rules from bounded edit observations, never full-word keys."""
    rules: list[RewriteRule] = []
    for index, row in enumerate(observations):
        pattern = str(row.get("pattern", ""))
        if not pattern or len(pattern) > int(row.get("max_context_length", 8)):
            continue
        rules.append(RewriteRule(index, str(row.get("operation", "replace")), str(row.get("spelling_left", "")), str(row.get("spelling_right", "")), str(row.get("pronunciation_left", "")), str(row.get("pronunciation_right", "")), pattern, str(row.get("replacement", "")), row.get("source_stage")))
        if len(rules) >= max_rules:
            break
    return tuple(rules)


# Names for the offline research strategies. They share the same normalized rule form.
TransformationErrorCandidates = induce_rewrite_rules
GreedyContextRuleCandidates = induce_rewrite_rules
MDLCandidates = induce_rewrite_rules
DecisionListCandidates = induce_rewrite_rules
RecursivePartitionCandidates = induce_rewrite_rules
SuffixPrefixCandidates = induce_rewrite_rules
TrieRecurringErrorCandidates = induce_rewrite_rules
