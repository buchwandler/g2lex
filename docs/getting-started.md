# Getting started

## Install

G2Lex supports Python 3.10 through 3.14 and has no mandatory runtime
dependencies:

```bash
python -m pip install g2lex
```

For development, install the test and lint tools with
`python -m pip install -e '.[dev]'`.

## Compile a source dictionary

A TSV file with a word and pronunciation can be compiled directly:

```bash
g2lex pack lexicon.tsv lexicon.g2lex --format tsv
```

Verify the compiled asset against its source before publishing it:

```bash
g2lex verify lexicon.tsv lexicon.g2lex --format tsv
```

## Read exact values

```python
import g2lex

with g2lex.open("lexicon.g2lex") as lexicon:
    pronunciation = lexicon.get("example")
    if pronunciation is not None:
        print(pronunciation)
```

`Lexicon` is a read-only mapping. Lookup is lazy and backed by a memory map;
closing the context releases the underlying resources. It is safe to use
`get()` when an application needs to select its own fallback for unknown words.

## Inspect and export

```bash
g2lex inspect lexicon.g2lex
g2lex export lexicon.g2lex restored.jsonl --format jsonl
g2lex diff first.g2lex second.g2lex
```

See [CLI](cli.md) for all stable commands and [source formats](source-formats.md)
for input-specific rules.
