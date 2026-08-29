# Benchmarking

Benchmarks are fixture-specific evidence, not a universal performance promise.
The repository benchmark compares JSON, TSV, SQLite, and G2Lex for source and
compiled bytes, cold open time, traced allocations, lookup percentiles, and
sequential iteration.

```bash
python -m benchmarks.runtime_storage.benchmark \
  tests/fixtures/generic.tsv --format tsv --repetitions 1000
```

For binary or runtime refactors, record at least asset size, cold open/load,
resident memory, lookup latency/throughput, iteration, and package size where
relevant. Use deterministic fixtures and lock external sources. Network access
must be an explicit opt-in; a full-source gate is preferable to silently
benchmarking a partial download.

A structural improvement that causes a meaningful mmap or resident-memory
regression requires a documented trade-off and should not be merged on unit
tests alone. Interpret results together with fixture size, cache state, and
Python version.
