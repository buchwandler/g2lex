---
schema_version: 2
object_type: release_entry
versioning:
  schema_version: 1
  revision: 1
entry_id: entry-0002
release_version: v0.1.0
kind: added
summary:
  Added indexed V4 assets with memory-mapped loading, bounded reconstruction,
  configurable selectors, and training support
status: accepted
audience: null
scopes: []
source_refs:
  - git:0832d8f64ebb0bcf0bb36b1ebf441237c0a8363d
paths:
  - .ledger/ledger.toml
  - .ledger/taskledger/.ledger-project.toml
  - .ledger/taskledger/config.toml
  - README.md
  - benchmarks/de_lexicon_entry_reduction/config.py
  - benchmarks/de_lexicon_entry_reduction/full_source_gate.py
  - benchmarks/de_lexicon_entry_reduction/run.py
  - benchmarks/de_lexicon_entry_reduction/run_config.py
  - benchmarks/de_lexicon_entry_reduction/sources.py
  - lexcompact/__init__.py
  - lexcompact/asset.py
  - lexcompact/asset_v4.py
  - lexcompact/audit.py
  - lexcompact/builder.py
  - lexcompact/composer.py
  - lexcompact/container.py
  - lexcompact/g2p.py
  - lexcompact/graphone.py
  - lexcompact/literals.py
  - lexcompact/membership.py
  - lexcompact/model.py
  - lexcompact/neural.py
  - lexcompact/reconstructors.py
  - lexcompact/resolver.py
  - lexcompact/runtime.py
  - lexcompact/selectors/__init__.py
  - lexcompact/selectors/base.py
  - lexcompact/selectors/forest.py
  - lexcompact/selectors/gbdt.py
  - lexcompact/selectors/logistic.py
  - lexcompact/selectors/priority.py
  - lexcompact/selectors/tree.py
  - lexcompact/training/__init__.py
  - lexcompact/training/alignment.py
  - tests/test_v4_contracts.py
issues: []
prs: []
sources:
  - git:0832d8f64ebb0bcf0bb36b1ebf441237c0a8363d
contributors: []
breaking: false
internal: false
order: 2
---
