# Experimental reduction

Reduction and reconstruction are alpha research APIs. Import them explicitly:

```python
from g2lex.experimental import ReductionConfig, reduce_lexicon
```

The reduction CLI is also explicitly experimental:

```bash
g2lex reduce source.tsv reduced.lxc --format tsv
g2lex experimental verify-reduced source.tsv reduced.lxc --format tsv
```

Reduction assets use identities such as `g2lex.asset.v3` and `g2lex.asset.v4`,
not the stable `G2LX`/`g2lex.lexicon.v1` identity. Legacy `lexcompact.asset.*`
files may be readable for compatibility. Their runtime reconstruction and
resource constraints differ from stable exact lookup.

Reduction metadata and recipes are validated by the experimental verifier. Where
a reduction format requires it, zero per-generated-word recipes is an invariant.
Consumers should pin the experimental API version and retain fixtures because
these interfaces may change independently of the stable root API.
