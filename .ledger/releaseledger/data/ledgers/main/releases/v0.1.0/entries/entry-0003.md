---
schema_version: 2
object_type: release_entry
versioning:
  schema_version: 1
  revision: 1
entry_id: entry-0003
release_version: v0.1.0
kind: quality
summary:
  Added reproducible German de-gold benchmarks with locked sources, ablation
  runs, and result aggregation
status: accepted
audience: null
scopes: []
source_refs:
  - git:36d3c51b9534c90329580557f3ec6f2f6607d75f
paths:
  - .codecrate.toml
  - benchmarks/de_lexicon_entry_reduction/aggregate_results.py
  - benchmarks/de_lexicon_entry_reduction/benchmark_memory.py
  - benchmarks/de_lexicon_entry_reduction/config.py
  - benchmarks/de_lexicon_entry_reduction/configs/german-v3-reference.toml
  - benchmarks/de_lexicon_entry_reduction/configs/german-v4-ablation.toml
  - benchmarks/de_lexicon_entry_reduction/full_source_gate.py
  - benchmarks/de_lexicon_entry_reduction/lock_source.py
  - benchmarks/de_lexicon_entry_reduction/run.py
  - benchmarks/de_lexicon_entry_reduction/run_config.py
  - benchmarks/de_lexicon_entry_reduction/source-locks/de-gold.json
  - benchmarks/de_lexicon_entry_reduction/tests/test_pack_manifest.py
  - lexcompact/asset_v4.py
  - lexcompact/audit.py
  - lexcompact/backends.py
  - lexcompact/builder.py
  - lexcompact/literals.py
  - lexcompact/membership.py
  - lexcompact/reports.py
  - lexcompact/runtime.py
issues: []
prs: []
sources:
  - git:36d3c51b9534c90329580557f3ec6f2f6607d75f
contributors: []
breaking: false
internal: false
order: 3
---
