# Layering

`LayeredLexicon` combines mappings with first-layer precedence while retaining
metadata about the selected layer.

```python
from g2lex import LayeredLexicon, LexiconLayer

stack = LayeredLexicon([
    LexiconLayer("user", user_lexicon, {}),
    LexiconLayer("domain", domain_lexicon, {}),
    LexiconLayer("base", base_lexicon, {}),
])

with stack:
    hit = stack.get_hit("word")
    if hit is not None:
        print(hit.value, hit.layer_name)
```

Resolution uses raw key presence, not truthiness. A present `None` or another
false-like value intentionally wins and prevents fall-through. Iteration yields
unique keys in configured layer order; it does not promise globally sorted
output.

The composite owns its child mappings. `close()` is idempotent and access after
close raises `ValueError`, just as it does for `Lexicon`.
