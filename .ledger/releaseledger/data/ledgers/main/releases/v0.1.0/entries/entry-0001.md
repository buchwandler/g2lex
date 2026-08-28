---
schema_version: 2
object_type: release_entry
versioning:
  schema_version: 1
  revision: 1
entry_id: entry-0001
release_version: v0.1.0
kind: added
summary:
  Added the Python package and CLI for lossless lexicon reduction with German
  profiles and exact reconstruction checks
status: accepted
audience: null
scopes: []
source_refs:
  - git:459f0f98a2166d385e57917c21a923aa48bb1d04
paths:
  - .codecrate.toml
  - .github/workflows/tests.yml
  - .gitignore
  - .pre-commit-config.yaml
  - AGENT_SPEC.md
  - NOTICE
  - README.md
  - VALIDATION.md
  - benchmarks/__init__.py
  - benchmarks/de_lexicon_entry_reduction/README.md
  - benchmarks/de_lexicon_entry_reduction/__init__.py
  - benchmarks/de_lexicon_entry_reduction/analyze_failures.py
  - benchmarks/de_lexicon_entry_reduction/benchmark_memory.py
  - benchmarks/de_lexicon_entry_reduction/download.py
  - benchmarks/de_lexicon_entry_reduction/download_sources.py
  - benchmarks/de_lexicon_entry_reduction/fixtures/toy.tsv
  - benchmarks/de_lexicon_entry_reduction/run.py
  - benchmarks/de_lexicon_entry_reduction/run_matrix.py
  - benchmarks/de_lexicon_entry_reduction/source_manifest.toml
  - benchmarks/de_lexicon_entry_reduction/sources.py
  - benchmarks/de_lexicon_entry_reduction/tests/test_download_setup.py
  - benchmarks/de_lexicon_entry_reduction/tests/test_entry_reduction.py
  - benchmarks/de_lexicon_entry_reduction/verify.py
  - examples/kokorog2p_de_loader.py
  - lexcompact/__init__.py
  - lexcompact/_version.py
  - lexcompact/asset.py
  - lexcompact/audit.py
  - lexcompact/boundary_rules.py
  - lexcompact/builder.py
  - lexcompact/cli.py
  - lexcompact/composer.py
  - lexcompact/diagnostics.py
  - lexcompact/io.py
  - lexcompact/kokoro.py
  - lexcompact/linkers.py
  - lexcompact/literals.py
  - lexcompact/membership.py
  - lexcompact/model.py
  - lexcompact/optimizer.py
  - lexcompact/prefix_index.py
  - lexcompact/profiles/__init__.py
  - lexcompact/profiles/german.py
  - lexcompact/py.typed
  - lexcompact/reduce.py
  - lexcompact/reports.py
  - lexcompact/resolver.py
  - lexcompact/rules.py
  - lexcompact/segmentation.py
  - lexcompact/selector.py
  - lexcompact/verify.py
  - pyproject.toml
  - tests/test_core.py
  - tests/test_io_cli.py
issues: []
prs: []
sources:
  - git:459f0f98a2166d385e57917c21a923aa48bb1d04
contributors: []
breaking: false
internal: false
order: 1
---
