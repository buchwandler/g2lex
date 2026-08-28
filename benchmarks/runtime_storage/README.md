# G2Lex runtime storage benchmark

Run the local comparison without downloading data:

```bash
python -m benchmarks.runtime_storage.benchmark tests/fixtures/generic.tsv \
  --format tsv --repetitions 1000
```

The benchmark compares JSON and TSV dictionaries, SQLite, and G2Lex. It reports
source and compiled bytes, cold open time, traced Python allocations, lookup
p50/p95/p99, and sequential iteration throughput. Results are measurements for
the supplied fixture, not general performance claims.
