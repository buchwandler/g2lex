# Validation record — Lexcompact V3 MVP

Date: 2026-08-28

This record separates measurements executed in this sandbox from figures reported by
the supplied KokoroG2P snapshot.

## 1. New KokoroG2P snapshot reconstruction

The newly supplied Codecrate pack was reconstructed with its generated standard-library
unpacker:

```bash
python -S context_kokorog2p.unpack.py context_kokorog2p.md \
  -o kokorog2p_reconstructed_v3 \
  --check-machine-header --strict --fail-on-warning --progress
```

Result: success. **539 files** were reconstructed. Machine-header/manifest validation
passed and `--fail-on-warning` did not fail.

The implementation basis inspected was:

```text
experiments/de_lexicon_entry_reduction/
```

The newest material changes relevant to Lexcompact V3 are:

- `lexreduce/resolver.py`: ephemeral recursive constituent resolution;
- `lexreduce/segmentation.py`: compact deterministic integer `SegmentationScorer`;
- recursive/scorer support in builder and runtime composer;
- recursive/scorer serialization and reload;
- optimizer propagation of linker/recursive/component/state/scorer settings;
- experiment CLI flags for recursive constituents, recursive depth, and segmentation
  scorer.

## 2. Upstream focused experiment tests

Executed in the reconstructed KokoroG2P repository:

```bash
python -m pytest -q   experiments/de_lexicon_entry_reduction/tests/test_entry_reduction.py
```

Result:

```text
14 passed, 1 skipped
```

The skipped test is the opt-in full built-in-data test. The reconstructed portable
snapshot does not contain:

```text
kokorog2p/de/data/de_gold.json
```

Therefore the full 738,427-word run was not independently rerun here.

The reports contained in the supplied snapshot continue to state:

| Metric | Source-reported result |
| --- | ---: |
| baseline logical words | 738,427 |
| retained literal words | 586,889 |
| implicit generated words | 151,538 |
| literal-entry reduction | 20.52% |
| per-generated-word recipes | 0 |
| missing words | 0 |
| extra membership hits | 0 |
| pronunciation mismatches | 0 |
| variant-order mismatches | 0 |
| target `<= 400,000` | not met |

These are source-reported figures, not fresh V3 full-data measurements.

## 3. Standalone V3 project layout

The project is intentionally flat:

```text
lexcompact/
benchmarks/
tests/
examples/
pyproject.toml
```

Confirmed: **no `src/` directory exists**.

V3 adds:

```text
lexcompact/resolver.py
lexcompact/segmentation.py
```

The single-file runtime format is now:

```text
format = lexcompact.asset.v3
schema = 3
```

The V3 loader also accepts `lexcompact.asset.v2` / schema 2 and defaults the newly
introduced runtime fields to non-recursive/no-scorer behavior.

## 4. Standalone tests

Collected tests:

```text
benchmarks/de_lexicon_entry_reduction/tests/test_download_setup.py: 3
benchmarks/de_lexicon_entry_reduction/tests/test_entry_reduction.py: 15
tests/test_core.py: 7
tests/test_io_cli.py: 2
```

Total: **27 tests**.

Executed:

```bash
python -m pytest -q
```

Result: **27 passed**.

Benchmark-only subset:

```bash
python -m pytest -q benchmarks/de_lexicon_entry_reduction/tests
```

Result: **18 passed**.

Coverage includes:

- exact ordered variants;
- exact positive/negative membership;
- deterministic DAFSA serialization;
- deterministic `.lxc` serialization;
- zero generated-word recipe table;
- German compound/boundary/linker rules;
- selector behavior;
- utility optimizer behavior;
- V3 ephemeral recursive constituents;
- V3 segmentation-scorer serialization/reload;
- independent verification;
- pinned download metadata and explicit network gating;
- CLI round trips.

## 5. V3 recursive reconstruction smoke test

Synthetic logical source:

```text
A   -> a
B   -> b
C   -> c
AB  -> ab
ABC -> abc
```

With:

```python
ReductionConfig(
    max_components=2,
    recursive_components=True,
    max_recursive_depth=4,
    segmentation_scorer=SegmentationScorer(),
)
```

Measured:

| Metric | Result |
| --- | ---: |
| baseline words | 5 |
| retained literals | 3 |
| implicit generated words | 2 |
| runtime per-generated-word recipes | 0 |
| `ABC` after serialized reload | `("abc",)` |
| exact verification | passed |

`AB` is omitted and can still act as an **ephemeral reconstructed constituent** while
regenerating `ABC`. No `AB -> recipe` record is persisted.

This synthetic result validates the mechanism only; it is not a claim about real-language
reduction ratios.

## 6. CLI/benchmark smoke test

Executed against the repository-local German-style toy fixture:

```bash
python -m lexcompact.cli reduce   benchmarks/de_lexicon_entry_reduction/fixtures/toy.tsv   /tmp/toy-recursive.lxc   --format tsv   --profile de-linkers   --recursive-components   --segmentation-scorer v2

python -m lexcompact.cli verify   benchmarks/de_lexicon_entry_reduction/fixtures/toy.tsv   /tmp/toy-recursive.lxc   --format tsv
```

Measured:

| Metric | Result |
| --- | ---: |
| logical source words | 9 |
| resident literal words | 6 |
| implicit words | 3 |
| literal-entry reduction | 33.33% |
| runtime per-generated-word recipes | 0 |
| missing words | 0 |
| false-positive membership hits | 0 |
| pronunciation mismatches | 0 |
| variant-order mismatches | 0 |
| lossless | yes |

The benchmark reproduction command with `--boundary-rules v2`, German linkers,
recursive constituents, and segmentation scorer also completed successfully and
reloaded/verified its `.lxc` candidate independently.

A small offline matrix run completed and wrote `matrix.json` plus independently
reloadable candidates.

## 7. Download setup

The standalone benchmark manifest retains the current supplied KokoroG2P immutable
remote coordinates, sizes, and SHA-256 values for:

- `gruut_espeak`;
- `crane_wiktionary`.

The repository adds only the local `toy` source to the copied manifest.

Executed without `--download`:

```bash
python -m benchmarks.de_lexicon_entry_reduction.download_sources   --source gruut_espeak
```

Result: exit code 2 with the expected explicit-network refusal.

Remote download itself was not performed in this sandbox.

## 8. Memory harness

The fresh-process memory/lookup benchmark command runs successfully on the toy
candidate, including generated-word latency metrics.

The toy process reported a candidate RSS delta of zero at the operating system's
measurement granularity. This is **not meaningful evidence** of production memory
savings and must not be extrapolated. Large-data RSS remains unmeasured here because
the full built-in German asset is absent.

## 9. Packaging and dynamic versioning

`pyproject.toml` discovers packages from the repository root and declares a dynamic
version resolved by `lexcompact._version.__version__`.

V3 fallback version:

```text
0.3.0.dev0
```

Executed offline:

```bash
python -m pip wheel . --no-build-isolation --no-deps -w /tmp/lexcompact-v3-wheel
python -m pip install . --no-build-isolation --no-deps   --target /tmp/lexcompact-v3-install
```

Result: successful build/install of:

```text
lexcompact-0.3.0.dev0-py3-none-any.whl
```

An import from the installed target successfully:

- built a recursive V3 candidate;
- serialized/reloaded it;
- reconstructed `ABC` as `("abc",)`;
- reported `per_generated_word_recipe_count == 0`.

Backward-compatibility smoke test:

1. a V2 source tree generated a `lexcompact.asset.v2` file;
2. the installed V3 loader opened it;
3. lookup returned the exact expected pronunciation;
4. V2 correctly defaulted to `recursive_components=False` and no segmentation scorer.

## 10. Boundaries of the evidence

Proven in this sandbox:

- strict reconstruction of the newly supplied KokoroG2P pack;
- upstream V3-focused experiment tests pass;
- V3 recursive generated constituents work after serialization/reload;
- V3 segmentation scorer survives serialization/reload;
- zero per-generated-word runtime recipes remains enforced;
- the standalone full test suite passes;
- the benchmark/download/test harness operates offline;
- the no-`src/` package builds and installs;
- V2 runtime assets remain loadable.

Not independently proven here:

- a new full 738,427-word V3 German reduction measurement;
- production memory savings on that full lexicon;
- remote-source downloads in this sandbox.
