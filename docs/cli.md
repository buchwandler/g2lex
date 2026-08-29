# Command-line interface

The console script is `g2lex`. Use `g2lex --help` for the installed version.

## Stable commands

```bash
g2lex pack SOURCE OUTPUT --format FORMAT
g2lex lookup ASSET WORD
g2lex inspect ASSET
g2lex verify SOURCE ASSET --format FORMAT
g2lex export ASSET OUTPUT --format FORMAT
g2lex diff FIRST SECOND
g2lex --version
```

`pack` selects a source adapter and writes an exact `.g2lex` asset. `lookup`
reads one value. `inspect` reports asset metadata. `verify` compares source and
compiled content. `export` writes a supported source representation, and `diff`
reports logical changes between assets.

Commands return a non-zero status for invalid paths, formats, malformed input,
incompatible assets, or failed exact comparisons. Error output is intended for
humans and stable machine-facing report formats should be consumed through the
explicit JSON options where provided.

## Experimental commands

Reduction commands are intentionally marked experimental:

```bash
g2lex reduce SOURCE OUTPUT --format tsv
g2lex experimental verify-reduced SOURCE ASSET --format tsv
```

Reduction assets are not `.g2lex` exact v1 assets. Keep them behind an explicit
experimental workflow and verify them with the corresponding command.
