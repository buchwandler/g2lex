# Python API

The stable root API is intentionally small. The main entry points are
`g2lex.open`, `open_bytes`, and `open_traversable` for reading compiled assets;
`pack_file`, `verify_file`, `export_file`, and `compare` for workflows.

```python
from g2lex import (
    CaseAliasMapping,
    LayeredLexicon,
    LexiconLayer,
    TaggedValue,
    WORD_ONLY,
    compare,
    open,
    open_bytes,
)
```

`Lexicon` implements a read-only `Mapping[str, LexiconValue]`. Values may be a
string, an ordered tuple of strings, `TaggedValue`, `WORD_ONLY`, or another
format-specific typed value accepted by the source adapter.

Exact mapping access preserves the source's typed value. Use the convenience methods
when a pronunciation consumer needs a normalized interface:

| Access         | Result                                 |
| -------------- | -------------------------------------- |
| `get()` / `[]` | Exact typed source value               |
| `lookup_all()` | Ordered pronunciation tuple            |
| `lookup()`     | First ordered pronunciation, or `None` |

`lookup_all()` and `lookup()` apply optional tag selection and fall back to the
`DEFAULT` tag. “First” means the first variant in source order, not a quality
ranking. A `WORD_ONLY` value and an unresolved selector have no pronunciation.

The same conversion is available for a raw value (including a `LayerHit.value`)
with the root exports `pronunciation_variants(value)` and
`first_pronunciation(value)`.

```python
with open("lexicon.g2lex") as lexicon:
    exact_value = lexicon["word"]           # typed value, unchanged
    variants = lexicon.lookup_all("word")    # tuple for pronunciation consumers
    first = lexicon.lookup("word")           # first source-ordered pronunciation
    print(exact_value, variants, first)
```

`open_bytes` is useful for an in-memory asset. `open_traversable` keeps an
importlib resource alive for the lifetime of the returned lexicon; see
[Package resources](package-resources.md).

`LayeredLexicon`, `LexiconLayer`, `LayerHit`, and `CaseAliasMapping` provide
explicit composition. A closed lexicon or layer stack rejects further access.

The `g2lex.experimental` namespace contains reduction and reconstruction APIs
that are not part of the stable root contract. Compatibility helpers under
`g2lex.kokoro` are deprecated; new code should use the generic resource and
layering APIs.
