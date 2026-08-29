"""Language-neutral lexicon and runtime data model."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from .membership import ExactMembership
from .types import PronunciationTuple
from .value import LexiconValue, logical_sha256, validate_value


class LiteralStore(Protocol):
    """Immutable exact spelling to ordered-pronunciation storage."""

    backend_id: str

    def __contains__(self, word: object) -> bool: ...
    def get(self, word: str, default: Any = None) -> PronunciationTuple | Any: ...
    def __getitem__(self, word: str) -> PronunciationTuple: ...
    def __iter__(self) -> Iterator[str]: ...
    def __len__(self) -> int: ...
    def prefixes(self, text: str, position: int = 0) -> tuple[str, ...]: ...

    @property
    def serialized_bytes(self) -> int: ...

    def serialize_sections(self) -> Mapping[str, bytes]: ...


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
    display_name: str | None = None
    language: str | None = None
    locale: str | None = None
    dialect: str | None = None
    provider: str | None = None
    source_url: str | None = None
    source_format: str | None = None
    source_sha256: str | None = None
    source_size_bytes: int | None = None
    pronunciation_alphabet: str | None = None
    pronunciation_separator: str | None = None
    role_namespace: str | None = None
    license_expression: str | None = None
    license_name: str | None = None
    license_url: str | None = None
    attribution: str | None = None
    generator: str | None = None
    parser_id: str | None = None


    def __post_init__(self) -> None:
        """Normalize legacy and canonical provenance names in memory."""
        source_sha256 = self.source_sha256 or (self.sha256 or None)
        source_size_bytes = (
            self.source_size_bytes if self.source_size_bytes is not None else self.size_bytes
        )
        source_format = self.source_format or (self.format or None)
        object.__setattr__(self, "source_sha256", source_sha256)
        object.__setattr__(self, "sha256", source_sha256 or "")
        object.__setattr__(self, "source_size_bytes", source_size_bytes)
        object.__setattr__(self, "size_bytes", source_size_bytes)
        object.__setattr__(self, "source_format", source_format)
        object.__setattr__(self, "format", source_format or "")

    def canonical_dict(self) -> dict[str, object]:
        """Return the modern provenance shape used by serialized manifests."""
        value = asdict(self)
        value.pop("sha256", None)
        value.pop("size_bytes", None)
        value.pop("format", None)
        value["source_sha256"] = self.source_sha256
        value["source_size_bytes"] = self.source_size_bytes
        value["source_format"] = self.source_format
        return value

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

    def runtime_unique(self) -> LexiconData:
        unique: dict[str, PronunciationTuple] = {}
        for word, values in self.entries.items():
            seen: set[str] = set()
            result: list[str] = []
            for value in values:
                if value not in seen:
                    seen.add(value)
                    result.append(value)
            unique[word] = tuple(result)
        return LexiconData(
            unique,
            self.source,
            self.physical_rows,
            {**self.metadata, "view": "runtime_unique"},
        )

    @classmethod
    def from_pairs(
        cls,
        *pairs: tuple[str, str],
        source: SourceInfo | None = None,
    ) -> LexiconData:
        entries: dict[str, list[str]] = {}
        for word, pronunciation in pairs:
            entries.setdefault(word, []).append(pronunciation)
        return cls(
            {word: tuple(values) for word, values in entries.items()},
            source or SourceInfo("toy"),
            len(pairs),
        )


class LiteralLexicon(Mapping[str, PronunciationTuple]):
    """Legacy resident pronunciation table implementing ``LiteralStore``."""

    backend_id = "dict-json-v3"

    def __init__(self, values: Mapping[str, Iterable[str]] | None = None) -> None:
        self._values = {
            word: tuple(pronunciations)
            for word, pronunciations in sorted(dict(values or {}).items())
        }
        lengths: dict[str, set[int]] = {}
        for word in self._values:
            if word:
                lengths.setdefault(word[0], set()).add(len(word))
        self._lengths_by_initial = {key: tuple(sorted(value)) for key, value in lengths.items()}

    def __getitem__(self, word: str) -> PronunciationTuple:
        return self._values[word]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __contains__(self, word: object) -> bool:
        return word in self._values

    def get(self, word: str, default: Any = None) -> PronunciationTuple | Any:
        return self._values.get(word, default)

    @property
    def words(self) -> tuple[str, ...]:
        return tuple(self._values)

    def prefixes(self, text: str, position: int = 0) -> tuple[str, ...]:
        if position >= len(text):
            return ()
        return tuple(
            text[position : position + length]
            for length in self._lengths_by_initial.get(text[position], ())
            if position + length <= len(text) and text[position : position + length] in self._values
        )

    @property
    def serialized_bytes(self) -> int:
        return len(self.serialize_sections()["literals.json"])

    def serialize_sections(self) -> Mapping[str, bytes]:
        import json

        data = json.dumps(
            {word: list(values) for word, values in self._values.items()},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return {"literals.json": data}


@dataclass(slots=True)
class TypedLexiconData:
    """Canonical source data for exact typed lexicons."""

    entries: dict[str, LexiconValue]
    source: SourceInfo = field(default_factory=SourceInfo)
    physical_rows: int | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized: dict[str, LexiconValue] = {}
        for word, value in self.entries.items():
            if not isinstance(word, str) or not word:
                raise TypeError("lexicon keys must be non-empty strings")
            validate_value(value)
            normalized[word] = value
        self.entries = normalized
        if self.physical_rows is None:
            self.physical_rows = len(self.entries)

    @property
    def words(self) -> tuple[str, ...]:
        return tuple(self.entries)

    @property
    def logical_sha256(self) -> str:
        return logical_sha256(self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self) -> Iterator[str]:
        return iter(self.entries)

    def items(self) -> Iterable[tuple[str, LexiconValue]]:
        return self.entries.items()

    def get(self, word: str, default: object = None) -> LexiconValue | object:
        return self.entries.get(word, default)


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
    literals: LiteralStore
    literal_index: Any
    membership: ExactMembership
    composer: Any
    metadata: dict[str, object] = field(default_factory=dict)
    runtime_program: Any | None = field(default=None, repr=False)
    _resolver: Any | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        from .runtime import RuntimeProgram

        if self.runtime_program is None:
            self.runtime_program = RuntimeProgram.from_composer(self.composer)
        if self.runtime_program.recursive_components:
            from .resolver import ComponentResolver

            self._resolver = ComponentResolver(
                self.membership,
                self.composer,
                self.literals,
                self.literal_index,
                max_depth=self.runtime_program.max_recursive_depth,
                max_states=self.runtime_program.max_states,
            )

    def lookup_all(self, word: str) -> PronunciationTuple:
        literal = self.literals.get(word)
        if literal is not None:
            return literal
        if not self.membership.contains(word):
            return ()

        from .resolver import ResolveContext

        context = ResolveContext() if self._resolver is not None else None
        assert self.runtime_program is not None
        generated = self.runtime_program.reconstruct(
            word,
            literals=self.literals,
            membership=self.membership,
            prefix_index=self.literal_index,
            resolver=self._resolver,
            context=context,
        )
        if generated is None:
            raise RuntimeError(f"known non-literal word could not be regenerated: {word!r}")
        return generated

    def lookup(self, word: str) -> str | None:
        values = self.lookup_all(word)
        return values[0] if values else None

    def is_known(self, word: str) -> bool:
        return self.membership.contains(word)

    @property
    def per_generated_word_recipe_count(self) -> int:
        return int(str(self.metadata.get("per_generated_word_recipe_count", 0)))

    @property
    def literal_word_count(self) -> int:
        return len(self.literals)

    @property
    def generated_word_count(self) -> int:
        return len(self) - len(self.literals)

    def metrics(self) -> CandidateMetrics:
        baseline_count = int(str(self.metadata.get("baseline_word_count", len(self))))
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
            return int(str(baseline_count))
        return int(self.membership.word_count)

    def __contains__(self, word: object) -> bool:
        return isinstance(word, str) and self.is_known(word)

    def iter_entries(self) -> Iterator[tuple[str, PronunciationTuple]]:
        for word in self:
            yield word, self.lookup_all(word)
