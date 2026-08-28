"""Language-neutral lexicon and runtime data model."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

PronunciationTuple = tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SourceInfo:
    """Provenance metadata for one source lexicon."""

    source_id: str = "file"
    revision: str | None = None
    sha256: str = ""
    license: str = ""
    provenance_status: str = ""
    parser_version: str = "1"
    view_version: str = "1"
    format: str = ""
    path: str | None = None
    size_bytes: int | None = None


@dataclass(slots=True)
class LexiconData:
    """Canonical logical lexicon preserving ordered pronunciation variants.

    The core intentionally treats spelling and pronunciation strings as opaque
    Unicode. No case folding, normalization, IPA parsing, or language-specific
    morphology is applied here.
    """

    entries: dict[str, PronunciationTuple]
    source: SourceInfo = field(default_factory=SourceInfo)
    physical_rows: int | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.entries = {
            str(word): tuple(str(value) for value in values)
            for word, values in self.entries.items()
        }
        if self.physical_rows is None:
            self.physical_rows = sum(len(values) for values in self.entries.values())

    @property
    def words(self) -> tuple[str, ...]:
        return tuple(self.entries)

    @property
    def variant_count(self) -> int:
        return sum(len(values) for values in self.entries.values())

    def lookup_all(self, word: str) -> PronunciationTuple:
        return self.entries.get(word, ())

    def lookup(self, word: str) -> str | None:
        values = self.lookup_all(word)
        return values[0] if values else None

    def is_known(self, word: str) -> bool:
        return word in self.entries

    def runtime_unique(self) -> "LexiconData":
        unique: dict[str, PronunciationTuple] = {}
        for word, values in self.entries.items():
            seen: set[str] = set()
            unique[word] = tuple(
                value for value in values if not (value in seen or seen.add(value))
            )
        return LexiconData(
            unique,
            self.source,
            sum(len(values) for values in unique.values()),
            {**self.metadata, "view": "runtime_unique"},
        )

    @classmethod
    def from_pairs(
        cls,
        *pairs: tuple[str, str],
        source: SourceInfo | None = None,
    ) -> "LexiconData":
        entries: dict[str, list[str]] = {}
        for word, pronunciation in pairs:
            entries.setdefault(word, []).append(pronunciation)
        return cls(
            {word: tuple(values) for word, values in entries.items()},
            source or SourceInfo("toy"),
            len(pairs),
        )


class LiteralLexicon(Mapping[str, PronunciationTuple]):
    """Read-only resident pronunciation table for literal words."""

    def __init__(self, values: Mapping[str, Iterable[str]] = ()) -> None:
        self._values = {
            word: tuple(pronunciations)
            for word, pronunciations in sorted(dict(values).items())
        }

    def __getitem__(self, word: str) -> PronunciationTuple:
        return self._values[word]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def get(self, word: str, default: Any = None) -> PronunciationTuple | Any:
        return self._values.get(word, default)

    @property
    def words(self) -> tuple[str, ...]:
        return tuple(self._values)


@dataclass(frozen=True, slots=True)
class CandidateMetrics:
    baseline_word_count: int
    literal_word_count: int
    generated_word_count: int
    per_generated_word_recipe_count: int = 0

    @property
    def entry_reduction_count(self) -> int:
        return self.generated_word_count

    @property
    def entry_reduction_rate(self) -> float:
        return (
            self.generated_word_count / self.baseline_word_count
            if self.baseline_word_count
            else 0.0
        )


@dataclass(slots=True)
class ImplicitLexicon(Mapping[str, str]):
    """Reloadable lossless lexicon with no per-generated-word recipe table."""

    source: SourceInfo
    literals: LiteralLexicon
    literal_index: Any
    membership: Any
    composer: Any
    metadata: dict[str, object] = field(default_factory=dict)

    def lookup_all(self, word: str) -> PronunciationTuple:
        literal = self.literals.get(word)
        if literal is not None:
            return literal
        if not self.membership.contains(word):
            return ()

        resolver = None
        context = None
        if self.composer.recursive_components:
            from .resolver import ComponentResolver, ResolveContext

            context = ResolveContext()
            resolver = ComponentResolver(
                self.membership,
                self.composer,
                self.literals,
                self.literal_index,
                max_depth=self.composer.max_recursive_depth,
                max_states=self.composer.max_states,
            )

        generated = self.composer.derive(
            word,
            literals=self.literals,
            prefix_index=self.literal_index,
            resolver=resolver,
            context=context,
        )
        if generated is None:
            raise RuntimeError(
                f"known non-literal word could not be regenerated: {word!r}"
            )
        return generated

    def lookup(self, word: str) -> str | None:
        values = self.lookup_all(word)
        return values[0] if values else None

    def is_known(self, word: str) -> bool:
        return self.membership.contains(word)

    @property
    def per_generated_word_recipe_count(self) -> int:
        return int(self.metadata.get("per_generated_word_recipe_count", 0))

    @property
    def literal_word_count(self) -> int:
        return len(self.literals)

    @property
    def generated_word_count(self) -> int:
        return len(self) - len(self.literals)

    def metrics(self) -> CandidateMetrics:
        baseline_count = int(self.metadata.get("baseline_word_count", len(self)))
        return CandidateMetrics(
            baseline_count,
            len(self.literals),
            baseline_count - len(self.literals),
            self.per_generated_word_recipe_count,
        )

    def __getitem__(self, word: str) -> str:
        value = self.lookup(word)
        if value is None:
            raise KeyError(word)
        return value

    def __iter__(self) -> Iterator[str]:
        return iter(self.membership.iter_words())

    def __len__(self) -> int:
        baseline_count = self.metadata.get("baseline_word_count")
        if baseline_count is not None:
            return int(baseline_count)
        return len(self.membership.iter_words())

    def __contains__(self, word: object) -> bool:
        return isinstance(word, str) and self.is_known(word)

    def iter_entries(self) -> Iterator[tuple[str, PronunciationTuple]]:
        for word in self:
            yield word, self.lookup_all(word)
