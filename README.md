# lexcompact

## V5 exact typed lexicons

Lexcompact also provides a lossless, typed V5 binary format for scalar pronunciations, ordered variants, tagged values, explicit null selectors, and membership-only words. V5 files use UTF-8 front-coded keys and independently compressed record blocks. Filesystem loading is mmap-backed and decodes records on demand.

```bash
lexcompact pack us_gold.json us_gold.lxc --format kokoro-json
lexcompact verify us_gold.json us_gold.lxc --format kokoro-json
lexcompact inspect us_gold.lxc
lexcompact export us_gold.lxc restored.jsonl --format jsonl
lexcompact lookup us_gold.lxc live
```

Use `lexcompact.reduce` for the existing experimental resident-entry reduction workflow. V5 does not flatten tagged records or create capitalization alias entries. `CaseAliasMapping` and `LayeredLexicon` provide compatibility and explicit raw-record precedence for consumers such as KokoroG2P.
`lexcompact` is a Python library and CLI for **lossless resident-entry reduction of pronunciation lexicons**.

This V3 MVP follows the newest supplied KokoroG2P
`experiments/de_lexicon_entry_reduction` implementation. It keeps the central
constraint from that experiment: a spelling may be removed from the resident
pronunciation table only when runtime code can reconstruct its **exact ordered
pronunciation tuple**, while the generated word itself has no per-word recipe,
split, ID record, or generated-word map.

## V3 changes

Compared with the previous MVP, V3 adds the latest experiment's recursive
constituent machinery:

- generated words may be used as **ephemeral constituents** of another generated
  word when `recursive_components` is enabled;
- ephemeral constituents are resolved from exact membership plus the same shared
  composer and are never persisted as word-specific recipes;
- recursion is bounded by `max_recursive_depth` and the shared state budget;
- a compact, versioned `SegmentationScorer` can replace the historical
  segmentation rank;
- recursive/scorer configuration is serialized in the `.lxc` runtime asset;
- the utility optimizer threads linker, recursion, component/state, and scorer
  configuration through every exact rebuild;
- V3 assets are emitted as `lexcompact.asset.v3`; the loader also accepts V2
  assets and defaults their new fields safely.

The default core remains language-neutral. Strings are opaque Unicode and the
default composition rule is exact pronunciation concatenation. German stress,
boundary, and linker rules are explicit optional profiles.

## Runtime representation

A runtime lexicon contains:

```text
ImplicitLexicon
├── literals               pronunciation-bearing retained spellings
├── literal_index          shared prefix index over literals
├── membership             exact DAFSA over every original spelling
├── composer
│   ├── shared rules
│   ├── optional selector
│   ├── optional linker table
│   ├── optional recursive constituent resolver
│   └── optional compact segmentation scorer
└── aggregate metadata
```

There is intentionally no:

```text
derived.json
recipes.json
generated.json
word-ids.json
split-by-word table
rule-by-word table
```

Lookup is exact:

1. return a literal pronunciation if the spelling is retained;
2. otherwise reject immediately unless the spelling is in the exact membership
   automaton;
3. reconstruct from retained literals/shared rules;
4. when enabled, recursively resolve known proper-substring constituents
   ephemerally;
5. raise an invariant error if a known omitted word cannot be reconstructed.

Exact membership is essential: arbitrary OOV strings that happen to be
compositionally possible must remain misses.

## V4 foundations

The V4 runtime exposes replaceable exact membership and literal-store contracts, a shared `RuntimeProgram`, ephemeral `ReconstructionCandidate` values, and non-copying `OverlayMapping` recursion. It includes packed membership and literal controls, deterministic reversible codecs, bounded CART and graphone G2P stages, morphology and rewrite stages, candidate selectors, and optional pure-data neural-family experiments.

V4 assets use the indexed `LXC4` container. Sections are sorted, aligned, hashed, and safe to load from a memory map. Legacy V2 and V3 ZIP assets remain supported by the dispatch loader.

Benchmark cases are configured in TOML and run with:

```bash
python -m benchmarks.de_lexicon_entry_reduction.run_config config.toml
```

The full German gate requires the exact source and refuses to claim results when it is unavailable.

## Repository layout

There is deliberately **no `src/` directory**:

```text
lexcompact/
benchmarks/de_lexicon_entry_reduction/
tests/
examples/
pyproject.toml
README.md
AGENT_SPEC.md
VALIDATION.md
```

## Install

```bash
python -m pip install -e .
python -m pytest
```

The version is dynamic. `pyproject.toml` reads
`lexcompact._version.__version__`, which derives versions from Git tags when
available, accepts `LEXCOMPACT_VERSION` as a release override, and falls back to
`0.3.0.dev0` for a source archive without Git metadata.

## CLI

Generic language-neutral reduction:

```bash
lexcompact reduce original.json reduced.lxc
lexcompact reduce original.tsv reduced.lxc --format tsv
```

Enable V3 recursive constituents and the compact segmentation scorer:

```bash
lexcompact reduce original.tsv reduced.lxc \
  --format tsv \
  --recursive-components \
  --max-recursive-depth 4 \
  --segmentation-scorer v2
```

German research profiles remain explicit:

```bash
lexcompact reduce de.json de.lxc --profile de-compound
lexcompact reduce de.json de.lxc --profile de-boundary
lexcompact reduce de.json de.lxc --profile de-linkers
```

These can be combined with the recursive/scorer flags.

Independent verification and runtime tools:

```bash
lexcompact verify original.tsv reduced.lxc --format tsv
lexcompact lookup reduced.lxc WORD
lexcompact inspect reduced.lxc
lexcompact restore reduced.lxc restored.tsv --format tsv
```

`restore` reconstructs the complete **logical** lexicon. It does not promise
byte-identical JSON formatting, TSV row layout, comments, or line endings.

## Python API

```python
from lexcompact import (
    ReductionConfig,
    SegmentationScorer,
    load,
    read_lexicon,
    reduce_lexicon,
    save,
)

source = read_lexicon("lexicon.tsv", format="tsv")

config = ReductionConfig(
    recursive_components=True,
    max_recursive_depth=4,
    segmentation_scorer=SegmentationScorer(),
)

build = reduce_lexicon(source, config=config)
save("lexicon.lxc", build.asset)

lexicon = load("lexicon.lxc")
assert lexicon.lookup_all("example") == source.lookup_all("example")
assert lexicon.is_known("example") == source.is_known("example")
```

`ImplicitLexicon` implements `Mapping[str, str]`; mapping access returns the first
pronunciation while `lookup_all()` preserves every ordered variant.

## Exactness contract

For every source spelling, a valid candidate must preserve:

- exact positive membership;
- exact negative membership for independently generated misses;
- exact pronunciation strings;
- exact variant count;
- exact variant order.

The offline builder may inspect expected pronunciation to decide whether a word
can be omitted. The runtime composer/resolver does not receive the baseline
lexicon or expected pronunciation.

Search-budget or recursion-limit exhaustion is conservative during building: the
word remains literal.

## Language scope

The core does not lowercase, casefold, normalize Unicode, tokenize IPA, strip
stress, infer morphology, or use approximate pronunciation matching.

The logical MVP model is:

```text
spelling: str
pronunciations: tuple[str, ...]
```

This works for phoneme lexica in any language when their data can be exposed in
that form. Context/POS-sensitive lexica should use an adapter that maps their
richer records to stable logical keys rather than putting language-specific
semantics into the core reducer.

## KokoroG2P integration

The German KokoroG2P path consumes a mapping-like lexicon, so a `.lxc` resource
can be loaded without materializing the full logical dictionary:

```python
import importlib.resources
from collections.abc import Mapping
from functools import lru_cache

from kokorog2p.de import data
from lexcompact import load_traversable


@lru_cache(maxsize=1)
def _load_gold_dictionary(load_gold: bool = True) -> Mapping[str, str]:
    if not load_gold:
        return {}
    return load_traversable(importlib.resources.files(data) / "de_gold.lxc")
```

Do not wrap the result in `dict(...)` during startup; that would materialize every
logical entry and defeat the resident-entry objective.

## Reproduced benchmark harness

The repository contains:

```text
benchmarks/de_lexicon_entry_reduction/
  README.md
  source_manifest.toml
  download.py
  download_sources.py
  sources.py
  run.py
  run_matrix.py
  verify.py
  benchmark_memory.py
  analyze_failures.py
  fixtures/toy.tsv
  tests/
```

The pinned source/download behavior from the surrounding KokoroG2P compression
experiment is retained, including immutable revisions, expected sizes, SHA-256
checks, revision-scoped cache paths, and explicit `--download` network opt-in.

V3-specific benchmark run:

```bash
python -m benchmarks.de_lexicon_entry_reduction.run \
  --source toy \
  --mode implicit-compound \
  --boundary-rules v2 \
  --linkers german \
  --recursive-components \
  --segmentation-scorer v2 \
  --output /tmp/lexcompact-v3
```

Then verify independently:

```bash
python -m benchmarks.de_lexicon_entry_reduction.verify \
  --source toy \
  --run /tmp/lexcompact-v3
```

## Source-reported German baseline

The supplied KokoroG2P reports still record this verified baseline candidate:

| Metric                             |  Result |
| ---------------------------------- | ------: |
| baseline logical words             | 738,427 |
| retained literal words             | 586,889 |
| implicit generated words           | 151,538 |
| literal-entry reduction            |  20.52% |
| per-generated-word runtime recipes |       0 |
| missing words                      |       0 |
| extra membership hits              |       0 |
| pronunciation mismatches           |       0 |
| variant-order mismatches           |       0 |
| target `<= 400,000`                | not met |

Those reports are retained as source evidence. The portable snapshot does not
contain the large `de_gold.json` payload, so this MVP does not relabel those
figures as a fresh full-data measurement.
