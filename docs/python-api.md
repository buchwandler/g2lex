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

```python
with open("lexicon.g2lex") as lexicon:
    value = lexicon.get("word")
    for word, pronunciation in lexicon.items():
        print(word, pronunciation)
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
