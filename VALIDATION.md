# Validation record: G2Lex 0.1.0 release candidate

## Environment

- Repository: `g2lex`
- Runtime used for local checks: CPython 3.14.6 on Android (Termux)
- Runtime dependencies: none
- Validation scope: the candidate workspace after the release-readiness fixes

## Source revision/tag

- Current Git `HEAD`: `1f281aeae6ac7fb772f3120055fd786c1597ee9c`
- Releaseledger stored snapshot: `4f34aba4434fe92331f68a52600f1dedf762ebc7`; it remains drifted because this candidate workspace is uncommitted.
- Final signed `v0.1.0` tag: not created
- GitHub Release: not created
- PyPI publication: not performed

## Unit/integration tests

```text
python -m pytest
193 passed
```

Recorded as taskledger check `check-0048`.

## Coverage

The canonical whole-package branch-aware coverage gate passed:

```text
python -m pytest --cov=g2lex --cov-branch --cov-report=term-missing --cov-report=json:coverage.json
Statements: 4,671 / 4,970 covered (93.98%)
Branches: 1,397 / 1,618 covered (86.34%)
Combined coverage: 92.11%
```

The CI gate is now 90% combined coverage with an independent 80% branch floor. Coverage targets the complete `g2lex` package and does not use ordinary coverage exclusions to hide missing tests.

Recorded as taskledger check `check-0049`.

## Ruff/pre-commit

- `python -m ruff check .`: passed, taskledger check `check-0044`
- `python -m ruff format --check .`: passed, taskledger check `check-0043`
- `pre-commit run --all-files`: passed, taskledger check `check-0047`

## Compilation and warning-clean tests

- `python -m compileall -q g2lex tests benchmarks examples scripts`: passed, taskledger check `check-0046`
- `python -W error::ResourceWarning -m pytest`: 193 passed, taskledger check `check-0045`
- `python -m pytest -W error::ResourceWarning -W error::pytest.PytestUnraisableExceptionWarning`: 193 passed

The Gruut SQLite adapter and its fixture now close connections explicitly.

## Package build

```text
python -m build
Successfully built g2lex-0.1.0.tar.gz and g2lex-0.1.0-py3-none-any.whl
python -m twine check dist/*
Checking dist/g2lex-0.1.0-py3-none-any.whl: PASSED
Checking dist/g2lex-0.1.0.tar.gz: PASSED
```

Recorded as taskledger checks `check-0049` and `check-0050`.

## Wheel install smoke test

A clean virtual environment installed `dist/g2lex-0.1.0-py3-none-any.whl`.
The installed command reported `g2lex 0.1.0` and completed a toy pack/verify
round trip with 9 source entries, 9 asset entries, and zero mismatches.

## Sdist install smoke test

A separate clean virtual environment installed `dist/g2lex-0.1.0.tar.gz`.
The installed command reported `g2lex 0.1.0` and completed the same lossless toy
pack/verify round trip with zero mismatches.

Both artifact smoke tests are recorded as taskledger check `check-0051`.

## CLI smoke test

The source CLI tests cover pack, lookup, inspect, export, convert, diff, restore,
verify, and experimental reduction verification. The final full suite and
coverage run passed.

## G2Lex v1 exact round trip

The exact source fixture round trips through the stable `G2LX` container. The
verification result reports:

```json
{
  "lossless": true,
  "source_entry_count": 9,
  "asset_entry_count": 9,
  "missing": 0,
  "extra": 0,
  "shape_mismatch": 0,
  "value_mismatch": 0,
  "tag_mismatch": 0,
  "null_mismatch": 0,
  "variant_order_mismatch": 0,
  "logical_sha256_match": true
}
```

## Corruption/integrity tests

The test suite covers corrupt headers, invalid varints, bounded decompression,
trailing compressed data, memory-mapped lifetimes, double close behavior, and
concurrent exact reads.

## Docs build

The MyST documentation tree now has `docs/index.md`, declares `myst-parser`, and
builds with warnings treated as errors:

```text
sphinx-build -W -b html docs docs/_build/html
build succeeded
```

The build passed from the repository root and `docs/make.py` passed from both the
repository root and the `docs` directory. These are recorded as taskledger checks
`check-0048`, `check-0014`, and `check-0015`.

## Python-version CI matrix

The GitHub Actions test matrix remains configured for Python 3.10, 3.11, 3.12,
3.13, and 3.14. The coverage, pre-commit, documentation, and package jobs are
configured in CI, but remote GitHub Actions results are not available in this
local validation record.

## Known experimental components

Experimental reduction remains separate from stable G2Lex v1. Newly written
reduction assets use `g2lex.asset.v3` and `g2lex.asset.v4`. Readers retain support
for legacy `lexcompact.asset.v2`, `lexcompact.asset.v3`, and
`lexcompact.asset.v4` identities. Experimental reduction APIs, selectors, and
reconstruction behavior may change during the alpha series.

## External source/full benchmark evidence

The repository retains its deterministic benchmark fixtures and source locks.
Network-dependent full-source benchmark execution is not part of this offline
candidate validation.

## Release decision

**Release candidate only. Do not publish.**

The local release gates are green for tests, whole-package coverage, warnings,
formatting, pre-commit, documentation, package metadata, wheel, sdist, and
installed artifact smoke tests. GitHub Actions matrix results and final PyPI name
availability still require release-day confirmation.

Releaseledger v0.1.0 is in `candidate` status with no release date. The changelog
was regenerated as an unreleased candidate section. No PyPI upload, GitHub
Release, or signed release tag was performed.
