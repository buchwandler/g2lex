# G2Lex

G2Lex compiles pronunciation dictionaries into deterministic, mmap-friendly
binary assets for exact, low-memory lookup from Python.

It is designed for G2P, TTS, ASR, forced alignment, and other speech systems
that need large read-only pronunciation lexicons without materializing the
entire dictionary as Python objects.

```bash
g2lex pack lexicon.tsv lexicon.g2lex --format tsv
g2lex lookup lexicon.g2lex example
g2lex inspect lexicon.g2lex
g2lex verify lexicon.tsv lexicon.g2lex --format tsv
g2lex export lexicon.g2lex restored.jsonl --format jsonl
g2lex diff first.g2lex second.g2lex
```

```python
import g2lex

with g2lex.open("lexicon.g2lex") as lexicon:
    print(lexicon["example"])
```

## Features

- Exact typed pronunciation lexicons
- Scalar and ordered pronunciation variants
- Context and role-tagged pronunciations
- Explicit null selector values
- Membership-only word sets
- Deterministic single-file G2Lex Binary Lexicon v1 assets
- mmap-backed lazy lookup
- Block compression with a bounded runtime cache
- Source SHA-256 and logical SHA-256 metadata
- JSON, JSONL, TSV, Kokoro JSON, CMUdict, MFA, PLS subset, and SQLite adapters
- Lexicon diffing and layering
- Importlib resource loading
- Zero mandatory runtime dependencies

## Not a phonemizer

G2Lex stores exact pronunciations. It does not predict pronunciations for
unknown words, normalize text, tokenize input, tag parts of speech, interpret
IPA, or run a fallback engine. Use it as the dictionary layer before eSpeak,
a neural G2P model, a rules engine, or another consumer-owned fallback.

```python
def pronounce(word: str, *, lexicon, fallback):
    value = lexicon.get(word)
    return value if value is not None else fallback(word)
```

## Python API

The stable package root contains the exact runtime and its source and layering
interfaces:

```python
from g2lex import (
    CaseAliasMapping,
    LayeredLexicon,
    LexiconLayer,
    TaggedValue,
    WORD_ONLY,
    open,
    open_bytes,
    open_traversable,
    pack_file,
    verify_file,
    export_file,
    compare,
)
```

`Lexicon` implements `Mapping[str, LexiconValue]`. Values may be strings,
ordered tuples of strings, `TaggedValue`, or `WORD_ONLY`.

Case aliases and layers are explicit utilities. A layer stack uses the first
layer containing the raw key, so a tagged record does not fall through to a
lower layer:

```python
lexicon = LayeredLexicon([
    LexiconLayer("user", user_lexicon, {}),
    LexiconLayer("domain", domain_lexicon, {}),
    LexiconLayer("base", base_lexicon, {}),
])
```

For package resources, retain the resource lifetime through the lexicon:

```python
from importlib.resources import files
import g2lex

resource = files(my_package.data) / "de_gold.g2lex"
with g2lex.open_traversable(resource) as lexicon:
    pronunciation = lexicon.get("haus")
```

## Source adapters

The source remains human-editable and can be compiled during a build or release
pipeline.

```bash
g2lex pack cmudict.dict cmudict.g2lex --format cmudict
g2lex pack dictionary.mfa dictionary.g2lex --format mfa
g2lex pack source.pls source.g2lex --format pls
g2lex pack lexicon.sqlite lexicon.g2lex --format gruut-sqlite
```

CMUdict numbered variants such as `WORD(2)` become ordered variants of `WORD`.
Plain MFA dictionaries are supported. MFA rows carrying probabilities or other
extra fields are rejected because G2Lex v1 does not silently discard weighted
data.

PLS support is a strict subset consisting of one lexicon language, one default
alphabet, one grapheme per lexeme, one or more phoneme values, and an optional
role. Aliases, examples, multiple graphemes, per-phoneme alphabet overrides,
and arbitrary metadata are rejected rather than flattened.

## Binary format

G2Lex Binary Lexicon v1 uses the public identity:

```text
magic:             G2LX
schema:            1
manifest:          g2lex.lexicon.v1
extension:         .g2lex
```

The implementation uses UTF-8 front-coded key blocks, ordinal records,
independently compressed record blocks, checksums, and memory mapping. The
runtime decodes keys and values on demand and keeps only a bounded cache of
decompressed record blocks.

The manifest records source and logical hashes plus optional language, locale,
provider, revision, pronunciation alphabet, role namespace, licensing,
attribution, generator, parser identity, and parser version fields. Pronunciation
strings remain opaque UTF-8 values.

## Experimental reduction

Resident-entry reduction and reconstruction research remains available, but is
not part of the stable root API. Import it explicitly:

```python
from g2lex.experimental import ReductionConfig, reduce_lexicon
```

The compatibility CLI command is also explicitly experimental in purpose:

```bash
g2lex reduce source.tsv reduced.lxc --format tsv
g2lex experimental verify-reduced source.tsv reduced.lxc --format tsv
```

Reduction assets use their own experimental loader and are not G2Lex v1 assets.
The exact `verify` command accepts only `.g2lex` assets, preventing an
experimental reduction file from being mistaken for an exact compiled lexicon.

## Benchmarks

The repository includes a local storage comparison. It measures JSON and TSV
dictionaries, SQLite, and G2Lex for source and compiled bytes, cold open time,
traced allocations, lookup percentiles, and sequential iteration:

```bash
python -m benchmarks.runtime_storage.benchmark \
  tests/fixtures/generic.tsv --format tsv --repetitions 1000
```

Results are fixture-specific measurements. The project does not promise a
particular compression ratio or performance advantage over SQLite without
benchmark evidence.

## Install and test

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
```

The package has no mandatory runtime dependencies. Source dictionaries and
compiled assets remain the responsibility of consumer projects and their
licensing or attribution requirements.
