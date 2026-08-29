# G2Lex

G2Lex compiles pronunciation dictionaries into deterministic, mmap-friendly binary
lexicons for exact Python lookup. It is designed for G2P, TTS, ASR, forced
alignment, and other speech systems that need large read-only dictionaries.

```{toctree}
:maxdepth: 2
:caption: User guide

getting-started
concepts
source-formats
binary-format-v1
python-api
cli
layering
package-resources
compatibility
experimental-reduction
benchmarking
changelog
validation-status
validation/v0.1.0
```

G2Lex stores exact pronunciations; it does not phonemize unknown words, normalize
text, tokenize input, or provide a fallback G2P engine. Use it as the dictionary
layer before a consumer-owned fallback.

## Quick start

```bash
python -m pip install g2lex
g2lex pack lexicon.tsv lexicon.g2lex --format tsv
g2lex verify lexicon.tsv lexicon.g2lex --format tsv
```

```python
import g2lex

with g2lex.open("lexicon.g2lex") as lexicon:
    print(lexicon.get("example"))
```

G2Lex 0.1.x is an alpha API and format release. The stable G2Lex Binary Lexicon
v1 format is intended to remain readable; experimental reduction APIs and assets
may change.
