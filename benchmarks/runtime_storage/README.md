# G2Lex runtime storage benchmark

Run the local comparison without downloading data:

```bash
python -m benchmarks.runtime_storage.benchmark tests/fixtures/generic.tsv \
  --format tsv --repetitions 1000
```

The benchmark compares JSON and TSV dictionaries, SQLite, and G2Lex. It reports
source and compiled bytes, cold open time, traced Python allocations, lookup
p50/p95/p99, sequential iteration throughput, and deterministic outer archive
measurements (gzip, XZ, and wheel-equivalent raw DEFLATE). Each case includes
net bytes saved and reduction percentage versus its source representation.

The `InternedBinaryPoolLiteralStore` is an experimental, benchmark-only
candidate. It globally interns pronunciation strings and complete ordered
variant tuples while retaining duplicate values and exact keys. It is not part
of stable G2LX serialization and must not be used to merge independently
licensed source assets. Promote it only after pinned full-source size, lookup,
open-time, and RSS evidence meets the migration review's merge criterion.

Results are measurements for the supplied fixture, not general performance claims.
