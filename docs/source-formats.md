# Source formats

G2Lex adapters are intentionally strict and preserve source-specific semantics.
All formats produce the same typed lexicon model, but they do not flatten
features that their source format represents differently.

| Format | Accepted input | Important behavior |
|---|---|---|
| `json` | JSON object mapping words to values | Typed values and deterministic key ordering are preserved. |
| `jsonl` | One JSON record per line | Records are decoded independently; malformed records are rejected. |
| `tsv` | Word and pronunciation columns | Empty required fields, malformed columns, and unsupported typed shapes are rejected. |
| `cmudict` | CMUdict word plus phonemes | Numbered variants such as `WORD(2)` become ordered variants. |
| `mfa` | Plain MFA dictionary rows | Weighted or extra fields are rejected rather than discarded. |
| `pls` | Strict single-language PLS subset | One grapheme per lexeme, one alphabet, phoneme values, and optional role. |
| `gruut-sqlite` | Gruut SQLite pronunciation table | Required schema and fields are validated; rows retain deterministic ordering. |
| `kokoro-json` | Kokoro JSON source | Legacy consumer shape is handled by the compatibility adapter. |
| `words` | One word per line | Blank lines and comments follow the word-list adapter contract. |

Duplicate words are handled by each adapter's documented source rules. Variant
order is meaningful and is retained. Tags and selectors are represented as typed
values rather than embedded in pronunciation strings.

Use the format name with `g2lex pack`:

```bash
g2lex pack cmudict.dict cmudict.g2lex --format cmudict
g2lex pack source.mfa dictionary.g2lex --format mfa
g2lex pack source.pls dictionary.g2lex --format pls
g2lex pack lexicon.sqlite dictionary.g2lex --format gruut-sqlite
```

Invalid UTF-8, missing required fields, and unsupported source shapes fail with a
contextual adapter error. Source metadata such as format, size, and digest is
recorded when available.
