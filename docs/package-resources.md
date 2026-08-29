# Package resources

Use `open_traversable` when a compiled lexicon is shipped inside an installed
package. The resource handle must remain alive while the lexicon is open.

```python
from importlib.resources import files
import g2lex

resource = files("my_package.data") / "de_gold.g2lex"
with g2lex.open_traversable(resource) as lexicon:
    pronunciation = lexicon.get("haus")
```

For a filesystem path, use `g2lex.open`. For bytes already loaded by an
application, use `g2lex.open_bytes`. All forms expose the same read-only lookup
contract and should be closed with a context manager.

The deprecated `g2lex.kokoro` helpers remain for compatibility but do not own
live lexicon handles or consumer profiles. New integrations should construct
resources and `LexiconLayer` stacks directly.
