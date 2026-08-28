# German lexicon entry-reduction reproduction

This directory reproduces the later KokoroG2P `experiments/de_lexicon_entry_reduction` research harness around the standalone `lexcompact` package.

The runtime contract is the same: generated words are never represented by a runtime word→recipe map. Exact membership is a compact DAFSA, and reconstruction is spelling-only from literals plus shared rules/indexes.

V3 also reproduces the newest experiment's optional ephemeral recursive constituent
resolver and compact `SegmentationScorer`. Recursive constituents are reconstructed
on demand and never persisted as generated-word recipes.

## Offline smoke test

```bash
python -m benchmarks.de_lexicon_entry_reduction.run \
  --source toy \
  --mode implicit-compound \
  --boundary-rules v2 \
  --linkers german \
  --recursive-components \
  --segmentation-scorer v2 \
  --output /tmp/lexcompact-entry-reduction

python -m benchmarks.de_lexicon_entry_reduction.verify \
  --source toy \
  --run /tmp/lexcompact-entry-reduction

python -m benchmarks.de_lexicon_entry_reduction.benchmark_memory \
  --source toy \
  --run /tmp/lexcompact-entry-reduction
```

## Pinned external sources

The source manifest is copied from the inspected KokoroG2P experiment. Remote files are revision-pinned and checksum-pinned. Downloading is never automatic:

```bash
python -m benchmarks.de_lexicon_entry_reduction.download_sources \
  --source gruut_espeak,crane_wiktionary \
  --download
```

`builtin` refers to KokoroG2P's `kokorog2p.de.data/de_gold.json`; it is available only when that resource is installed/present. The portable Codecrate snapshot used to create this MVP did not contain the JSON payload.

## Matrix and diagnostics

```bash
python -m benchmarks.de_lexicon_entry_reduction.run_matrix \
  --source builtin \
  --output benchmarks/de_lexicon_entry_reduction/runs/matrix

python -m benchmarks.de_lexicon_entry_reduction.analyze_failures \
  --source builtin \
  --run benchmarks/de_lexicon_entry_reduction/runs/v1 \
  --output benchmarks/de_lexicon_entry_reduction/runs/v1/diagnostics
```

The benchmark code is repository tooling and is excluded from the installed wheel.
