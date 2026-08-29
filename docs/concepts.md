# Concepts

## Source and compiled lexicons

A source lexicon is human-editable input. A compiled `.g2lex` asset is a
validated, deterministic representation intended for distribution and repeated
read-only lookup. Compilation preserves typed values and source ordering rules
rather than interpreting pronunciation strings.

## Exact and lossless semantics

G2Lex records exact values: a scalar pronunciation, ordered variants, tagged
values, selector values, or the word-only sentinel. It does not normalize words,
interpret IPA, infer missing pronunciations, or silently discard source fields.

## Exact and pronunciation lookup

Mapping access is exact and lossless: `lexicon.get(word)` and `lexicon[word]`
return the original typed value. `lexicon.lookup_all(word)` converts a
pronunciation-capable value to an ordered tuple, while `lexicon.lookup(word)`
returns its first pronunciation or `None`. “First” always means source order, not
quality ranking. These convenience methods also support tagged values and their
`DEFAULT` fallback; `WORD_ONLY` and unresolved selectors produce no pronunciation.

## Lazy loading and memory mapping

Keys and record blocks are decoded on demand. Independently compressed blocks and
a bounded cache avoid materializing the complete dictionary in Python memory.
`Lexicon.close()` is idempotent; operations after close raise `ValueError`.

## Hashes and determinism

Physical bytes are deterministic for the same logical input. The manifest may
contain a source SHA-256 and a logical SHA-256. The logical hash describes the
canonical key/value content and is independent of incidental source metadata.

## Layers

`LayeredLexicon` composes read-only mappings with explicit precedence. It checks
raw key presence, so a false-like value or `None` can intentionally mask a lower
layer. See [Layering](layering.md).

## Stable and experimental APIs

The root package is the stable exact-lexicon API. Reduction and reconstruction
research is exposed explicitly through `g2lex.experimental`; its assets and
identities are not interchangeable with stable G2LX v1 assets. See
[Experimental reduction](experimental-reduction.md).
