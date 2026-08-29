# Compatibility

G2Lex 0.1.x is an alpha API and format release. The stable root API and G2LX
Binary Lexicon v1 are the compatibility surface described in this site.

## Read compatibility

Readers retain explicitly supported legacy fields and asset identities. Legacy
provenance names are normalized at decode boundaries, while old assets remain
readable. Experimental readers accept legacy `lexcompact.asset.v2`, `.v3`, and
`.v4` identities where documented.

## Stable versus experimental

Stable `.g2lex` assets contain exact lexicon values and are verified with the
stable `verify` workflow. Reduction assets use experimental identities such as
`g2lex.asset.v3` and `g2lex.asset.v4`; they must not be treated as exact v1
assets.

Existing imports from the root package and `g2lex.selectors` remain supported.
Deprecated compatibility helpers are kept visibly separate from canonical APIs
and may be removed only in a documented future release.

When upgrading, retain golden assets and run exact source round-trip tests. Do
not depend on private module layout, undocumented metadata keys, or compression
implementation details.
