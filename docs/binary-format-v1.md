# G2Lex Binary Lexicon v1

This page describes the compatibility contract, not private implementation
details.

## Identity

```text
magic:     G2LX
schema:    1
manifest:  g2lex.lexicon.v1
extension: .g2lex
```

## Contract

- The same logical input produces deterministic output bytes.
- Keys and typed values have canonical ordering and encoding.
- Section and record integrity is checked while opening and reading.
- Corrupt, truncated, or incompatible assets are rejected rather than partially
  served.
- Logical content can be compared independently from physical representation.
- File-backed lexicons own their mapped resource and release it on `close()`.
- Legacy compatibility is limited to formats explicitly documented by the API;
  experimental reduction identities are not stable v1 assets.

The manifest can carry source and logical hashes plus language, locale, provider,
revision, pronunciation alphabet, role namespace, licensing, attribution,
generator, and parser information. Pronunciation strings remain opaque UTF-8
values.

Use `g2lex verify` or `g2lex.compare` to check exact source equivalence. Do not
rely on undocumented section layout, compression choices, or cache behavior as a
serialization promise.
