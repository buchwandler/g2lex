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

## Crane German Wiktionary benchmark

The first-class Crane benchmark consumes the raw German Wiktionary TSV from the existing immutable manifest record:

- repository: `crane-local-ai/g2p-lexicons` (Hugging Face dataset)
- file: `de/de.tsv`
- revision: `bfd51698069a30e1b20bbf54479b55af50b4161d`
- SHA-256: `04a3909f07cd08615157393814188b420a7c3c5035cf7a0608d31be07892be29`
- license: `CC-BY-SA-4.0`

The upstream dataset card describes approximately 900k physical rows, but that is metadata rather than the measured baseline. Lexcompact reports the exact physical row count, the logical spelling count after its TSV view, ordered pronunciation variants, and duplicate-identical rows removed. Repeated spellings remain ordered variants and are not normalized, lowercased, or casefolded. The primary reduction rate is calculated from logical spellings, not physical rows. The `<=400,000` target is a cross-corpus stretch target and is not directly comparable with the built-in KokoroG2P 738,427-word source.

Downloading is explicit and the raw pinned file is used directly. Do not use the Hugging Face dataset viewer, whose current multi-file schema issue is unrelated to this raw-file benchmark.

Run the benchmark with the default revision-scoped cache:

```bash
python -m benchmarks.de_lexicon_entry_reduction.download_sources \
  --source crane_wiktionary \
  --download

python -m benchmarks.de_lexicon_entry_reduction.run_config \
  benchmarks/de_lexicon_entry_reduction/configs/crane-wiktionary-v4-benchmark.toml
```

The configuration runs these V4 cases: `a0-v4-concat-control`, `a1-v4-german-compound`, `a2-v4-existing-strong`, and `a3-v4-existing-strong-utility`. Each case must serialize and reload before exact verification, adversarial-miss checks, runtime anti-cheating audit, and fresh-process measurements. Results include source shape, reduction, section sizes, build and reload timings, lookup throughput and latency, raw process repetitions, and RSS/PSS deltas. Missing OS metrics are reported as `N/A` or `null`, never as fabricated zeroes.

Aggregate completed case directories with:

```bash
python -m benchmarks.de_lexicon_entry_reduction.aggregate_results \
  benchmarks/de_lexicon_entry_reduction/runs/crane-wiktionary-v4
```

This benchmark is not run in normal CI and ordinary imports/tests do not access the network. The full run must fail when the exact pinned source is absent or its checksum/size is wrong. A fixture run is only a network-free correctness smoke test and must never be used as the production result table. Retain the CC-BY-SA-4.0 provenance in generated metadata and report the exact measured source statistics in any published results.

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
