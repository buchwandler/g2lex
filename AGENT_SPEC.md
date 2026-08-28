# Coding-agent specification: extract KokoroG2P lexicon entry reduction into `lexcompact`

## 1. Objective

Turn the later KokoroG2P `experiments/de_lexicon_entry_reduction` work into an independent Python package and CLI whose primary metric is **resident pronunciation-entry count**, not archive byte compression.

The package must support phoneme/pronunciation lexica for arbitrary languages and scripts. German-specific composition logic may exist as an explicit optional profile, but the core library and default CLI behavior must not assume German orthography, German morphology, IPA, Kokoro's phoneme inventory, NFC normalization, lowercase keys, or any particular alphabet.

The central requirement is **lossless logical entry-number reduction**:

- the original logical spelling set must remain exact;
- every original spelling must return the exact original ordered pronunciation tuple;
- no spelling that was absent from the source may become a lexicon hit;
- omitted words must not require a word→recipe, word→split, word→rule, word-ID, or equivalent per-generated-word runtime table;
- the reduced asset must load independently of the source lexicon.

This repository intentionally uses a flat package layout:

```text
lexcompact/
benchmarks/
tests/
pyproject.toml
```

Do **not** introduce a `src/` directory.

---

## 2. Source basis inspected

The implementation was derived from the new KokoroG2P snapshot's `experiments/de_lexicon_entry_reduction`, not the older `de_lexicon_compression` entry-recipe approach.

The inspected experiment states the runtime contract explicitly:

- the builder may inspect canonical pronunciations while deciding whether a word can be omitted;
- the runtime composer is spelling-only and does not receive the baseline lexicon or expected pronunciation;
- exact membership is retained separately in a compact deterministic automaton;
- runtime assets reload without the source lexicon;
- exact pronunciation variant order is preserved;
- generated words have zero per-word runtime recipes.

The latest supplied reports all record the same verified German result:

| Metric                             |     Result |
| ---------------------------------- | ---------: |
| Baseline logical words             |    738,427 |
| Retained literal words             |    586,889 |
| Implicit generated words           |    151,538 |
| Literal-entry reduction            |     20.52% |
| Target literals                    | <= 400,000 |
| Target met                         |         no |
| Per-generated-word runtime recipes |          0 |
| Missing words                      |          0 |
| Extra membership hits              |          0 |
| Pronunciation mismatches           |          0 |
| Variant-order mismatches           |          0 |

The new experiment also contains additional research machinery absent from the earliest version:

- bounded deterministic segmentation;
- a two-part fast path;
- compact literal prefix indexing;
- exact DAFSA membership;
- shared composition-rule serialization;
- German compound-stress rules;
- diagnostic boundary rules;
- bounded shared German linker definitions;
- a compact rule selector trained offline without expected IPA in the runtime representation;
- utility-based literal-basis promotion;
- anti-cheating runtime audits;
- independent verification;
- fresh-process memory/load benchmarks;
- failure forensics and top-k segmentation analysis;
- a matrix runner.

All of those concepts should remain available or reproducible in the standalone repository.

### V3 delta from the newest supplied snapshot

The newest snapshot adds two important runtime/build capabilities that must be
preserved in this standalone V3 MVP:

1. **Ephemeral recursive constituents.** With `recursive_components=True`, a known
   omitted word may act as a constituent of another omitted word. It is resolved
   recursively from exact membership plus the same shared composer. No generated
   constituent is inserted into a persistent word table and no per-word recipe is
   serialized. Resolution is guarded by a memo, recursion stack, maximum depth,
   proper-substring segmentation, and the shared state budget.
2. **Compact segmentation scorer.** `SegmentationScorer` stores fixed integer
   weights over bounded generic constituent features. It changes deterministic
   spelling segmentation ranking without consulting expected pronunciation.
   Its complete configuration is small, versioned, serializable runtime state.

The new snapshot threads these features through `ImplicitComposer`,
`ComponentResolver`, `build_implicit_lexicon`, `optimize_basis`, serializer/load,
and the experiment CLI. V3 must do the same.

---

## 3. Critical architectural correction versus the older MVP

Do not restore the old `derived[word] = components` representation, even if it is serialized compactly.

A per-generated-word recipe table can reduce pronunciation payload bytes, but it does not fully satisfy the resident-entry-count goal because every omitted spelling still has its own recipe record. The later KokoroG2P experiment intentionally removed this structure.

The new runtime representation must be conceptually:

```text
ImplicitLexicon
├── literals               # pronunciation-bearing spelling -> variants
├── literal_index          # shared index over literal spellings
├── membership             # exact DAFSA over every original spelling
├── composer
│   ├── shared rules
│   ├── optional shared selector
│   ├── optional shared linker table
│   ├── optional ephemeral ComponentResolver
│   └── optional compact SegmentationScorer
└── metadata               # aggregate counts/config, never per-generated-word data
```

For a lookup:

```text
word
  |
  +-- direct literal? ---- yes ---> return stored pronunciation tuple
  |
  +-- exact member? ------ no ----> miss
  |
  +-- spelling-only composer -----> regenerate from retained literals/shared rules
                                    |
                                    +-- optional recursive resolver
                                    |     |
                                    |     +-- known proper substrings only
                                    |     +-- ephemeral memo/stack only
                                    |
                                    +-- failure => runtime invariant error
```

The membership gate is mandatory. Composition by itself must never authorize a hit because arbitrary out-of-vocabulary strings can be composable from valid atoms.

---

## 4. Language-neutral logical model

The installed package's canonical MVP model is:

```python
spelling: str
pronunciations: tuple[str, ...]
```

Both strings are opaque Unicode. Preserve them exactly.

The core must not:

- call `.lower()` or `.casefold()`;
- normalize Unicode;
- split phonemes into IPA symbols;
- strip or reinterpret stress;
- infer morphology;
- use edit distance or approximate phoneme equality;
- infer a language from characters;
- insert Kokoro-specific normalization.

The default shared rule is exact constituent pronunciation concatenation. A word may be omitted only if this rule's output tuple equals the source tuple exactly.

Language-specific profiles are opt-in. The German profile exists to reproduce the inspected experiment, not to define the core.

### Context/POS-sensitive lexica

Some lexica have values richer than `str` or ordered variants, for example `word -> {DEFAULT, VERB, ...}`. Do not contaminate the core composer with one consumer's schema. Add adapters that expose context-specific pronunciations as stable logical records/keys, or extend the format-adapter layer with a typed schema. The reduction engine should continue operating on opaque logical keys and ordered pronunciation tuples.

---

## 5. Builder algorithm

Use a deterministic shortest-first construction order:

```python
sorted(source.words, key=lambda word: (len(word), word))
```

In the default mode, components come only from the current retained-literal basis.
In the V3 opt-in recursive mode, already-known proper-substring words may also be
resolved **ephemerally** through `ComponentResolver`. A recursively generated
constituent is never inserted into the literal dictionary, membership table,
metadata, or a recipe table merely because it was used during a derivation.

For each word:

1. obtain the expected ordered pronunciation tuple from the canonical source;
2. ask the spelling-only composer for a candidate using current literals/indexes/shared rules;
3. if recursive mode is enabled, allow the resolver to reconstruct known
   proper-substring constituents under the depth/state bounds;
4. if the candidate tuple equals expected exactly, omit the word from literals;
5. otherwise retain the word and add it to the literal prefix index;
6. if bounded search or recursion exhausts its budget, retain the word conservatively.

After all words:

1. build exact DAFSA membership from the complete source word set;
2. verify DAFSA enumeration equals sorted source membership;
3. record aggregate metadata only;
4. construct the runtime asset.

Never feed expected pronunciation to the runtime composer.

---

## 6. Runtime composition

### Segmentation

The source experiment uses a bounded deterministic segmentation search plus a direct two-part fast path.

Ranking is historical and deterministic:

```python
(-component_count, component_lengths, reversed_components)
```

The runtime should use no pronunciation evidence to choose a spelling segmentation.

V3 may optionally use `SegmentationScorer`, a versioned set of fixed integer
weights over generic features (`component_count`, one-character components,
short components, length variance, and boundary count). The scorer is shared
runtime state; it must not contain word IDs, expected IPA, or per-word labels.

Search limits and recursion limits are safety/performance controls, not
approximation controls. If offline construction reaches a limit, the word remains literal.

### Rules

Rules are shared global objects. A rule may inspect:

- the queried spelling;
- the selected component spellings;
- pronunciation tuples of the retained components;
- bounded generic features derived from those values.

A rule must not inspect:

- source expected pronunciation;
- a generated-word identity table;
- a per-word split/rule/repair table;
- a hidden baseline mapping.

`ConcatenationRule` is the only default rule.

The German reproduction additionally includes:

- `CompoundStressDemotionRule` (`C1`);
- `FinalComponentStressDemotionRule` (`C2`);
- `BoundaryStressClassRule` (`C3`).

These are serialized shared rules, not word-specific repairs.

### Linkers

The German experiment's Fugenelement support is represented by a small shared `LinkerTable`, initially containing spellings such as `s`, `es`, `n`, `en`, `e`, `er`, and `ens`. The table may enumerate bounded linker candidates from the input spelling and retained literals.

Do not store which linker a particular generated word used.

### Selector

The later experiment includes a bounded `RuleSelector`. Training happens offline from exact outcomes, but the returned runtime selector stores only generic predicates/features and rule IDs.

The runtime selector must not store expected pronunciation or word identity. The anti-cheating audit should enforce a serialized byte limit and reject suspicious per-word fields.

---

## 7. Membership index

Use an exact deterministic acyclic finite-state automaton as in the source experiment.

Required properties:

- exact positive membership;
- exact negative membership;
- deterministic construction/serialization;
- no Bloom-filter false positives;
- no hash-collision semantics;
- no generated-word recipe data;
- offline enumeration available for verification.

`MembershipIndex.contains()` is on the runtime lookup path. `iter_words()` is primarily an audit/restore helper.

Potential later optimization: replace JSON DAFSA serialization with a compact binary encoding while preserving exactly the same logical contract. Do not weaken exact membership to save bytes.

---

## 8. Asset format

The MVP uses one deterministic `.lxc` ZIP container to satisfy the original CLI requirement that one original lexicon file produces one reduced runtime file.

Members:

```text
manifest.json
literals.json
literal-index.json
membership.dafsa
rules.json
composer.json
```

Forbidden members include:

```text
derived.json
recipes.json
generated.json
word-ids.json
splits.json
rule-by-word.json
```

The ZIP writer fixes member timestamps and sorting so repeated serializations are byte-deterministic for identical runtime state.

`manifest.json` contains aggregate counts/provenance/config. `composer.json` contains bounded shared composer configuration and aggregate metadata, including V3's `recursive_components`, `max_recursive_depth`, and optional serialized `SegmentationScorer`. Neither may contain per-generated-word information.

The standalone V3 container identifies itself as `lexcompact.asset.v3` / schema 3. The loader may accept V2 assets by defaulting the new fields to
non-recursive/no-scorer behavior.

The runtime loader must never open the original source lexicon.

---

## 9. CLI contract

The installed console script is `lexcompact`.

### Generic reduction

```bash
lexcompact reduce original.json reduced.lxc
lexcompact reduce original.tsv reduced.lxc --format tsv
```

Default behavior must be language-neutral exact concatenation.

### Optional German research profiles

```bash
lexcompact reduce de.json de.lxc --profile de-compound
lexcompact reduce de.json de.lxc --profile de-boundary
lexcompact reduce de.json de.lxc --profile de-linkers
```

These flags are explicit and should be described as reproducing experimental shared rules, not universally correct German morphology.

V3 composition controls are language-neutral and may be combined with any profile:

```bash
lexcompact reduce lexicon.tsv lexicon.lxc --format tsv \
  --recursive-components \
  --max-recursive-depth 4 \
  --segmentation-scorer v2
```

### Independent verification

```bash
lexcompact verify original.json reduced.lxc
```

Exit nonzero on any mismatch.

### Runtime diagnostics

```bash
lexcompact lookup reduced.lxc WORD
lexcompact inspect reduced.lxc
lexcompact restore reduced.lxc restored.json --format json
```

`restore` materializes the complete logical lexicon and is an important audit feature.

---

## 10. Parser contract

MVP parsers:

### JSON

Accept:

```json
{
  "word": "phonemes",
  "variant-word": ["first", "second"]
}
```

### TSV

Headerless two-column UTF-8:

```text
word<TAB>phonemes
word<TAB>second-variant
```

Repeated spellings represent ordered variants. Runtime-unique semantics remove duplicate-identical variants while retaining first occurrence order, matching the source experiment's `runtime_unique()` view.

Do not strip pronunciation content other than line terminators required to parse TSV rows.

---

## 11. KokoroG2P integration target

The inspected new KokoroG2P German loader is in `kokorog2p/de/lexicon.py`. `_load_gold_dictionary()` currently:

1. resolves `kokorog2p.de.data` with `importlib.resources.files()`;
2. opens `de_gold.json`;
3. parses the complete JSON dictionary;
4. wraps it in `MappingProxyType`;
5. caches the mapping with `@lru_cache(maxsize=1)`.

`GermanLexicon.lookup()` lowercases the query and then calls `self._gold.get(word_lower)`. Therefore `ImplicitLexicon`, which implements `Mapping[str, str]` and `.get()`, is compatible with this consumer shape.

Suggested KokoroG2P migration:

```python
from lexcompact import load_traversable

@lru_cache(maxsize=1)
def _load_gold_dictionary(load_gold: bool = True) -> Mapping[str, str]:
    if not load_gold:
        return MappingProxyType({})
    files = importlib.resources.files(data)
    return load_traversable(files / "de_gold.lxc")
```

Then package `de_gold.lxc` instead of, or temporarily alongside, `de_gold.json`.

### Integration acceptance tests

Add tests in KokoroG2P that compare legacy JSON and reduced asset lookups for every baseline word before removing the legacy resource. Test:

- `.lookup()` equivalence;
- `.is_known()` equivalence;
- `len()` equivalence;
- stress stripping above the mapping remains unchanged;
- OOV behavior remains unchanged;
- fallback selection remains unchanged;
- cache clear/cache info behavior remains unchanged;
- no source JSON is opened when reduced mode is used.

Do not remove the old JSON until the reduced asset has been generated from the exact release-pinned source and independently verified.

---

## 12. Reproduced benchmark harness

The standalone repository contains:

```text
benchmarks/de_lexicon_entry_reduction/
├── README.md
├── source_manifest.toml
├── sources.py
├── download.py
├── download_sources.py
├── run.py
├── run_matrix.py
├── verify.py
├── benchmark_memory.py
├── analyze_failures.py
├── fixtures/toy.tsv
└── tests/
```

This is intentionally under `benchmarks/`, not installed in the wheel.

### Source manifest

The KokoroG2P pins are retained:

- `builtin`: `kokorog2p.de.data/de_gold.json`;
- `gruut_espeak`: `beshkenadze/kokoro-ipa-lexicons`, immutable revision `8f96c76fbc3a6d22860332be1a5daf40acd7ca7a`, `de_lexicon.tsv`, SHA-256 `de725f8a6540ef7ddaefe3589eb54dda7fd527f9a71854a76011d2a35aba5cb5`;
- `crane_wiktionary`: `crane-local-ai/g2p-lexicons`, immutable revision `bfd51698069a30e1b20bbf54479b55af50b4161d`, `de/de.tsv`, SHA-256 `04a3909f07cd08615157393814188b420a7c3c5035cf7a0608d31be07892be29`.

A repository-local `toy` source is added only to keep CI/network-free reproduction possible.

### Download behavior

Network access must be explicit:

```bash
python -m benchmarks.de_lexicon_entry_reduction.download_sources \
  --source gruut_espeak,crane_wiktionary \
  --download
```

Rules:

- no download at import time;
- no download during normal tests;
- revision-scoped cache paths;
- SHA-256 check before accepting cached or downloaded data;
- atomic installation of downloaded files;
- actionable checksum/source errors.

### Reproduction run

```bash
python -m benchmarks.de_lexicon_entry_reduction.run \
  --source builtin \
  --mode implicit-compound \
  --output benchmarks/de_lexicon_entry_reduction/runs/v1
```

Run independent verification after serialization/reload, not against the in-memory builder object only.

### Matrix

Keep the source experiment's bounded matrix over component counts, concat/compound rules, and greedy/utility optimization. Selector, boundary, and linker stages can be run as explicit additional configurations.

### Fresh-process measurement

Memory/load measurements must happen in separate Python processes. In-process `sys.getsizeof()` is not sufficient for the user goal because the baseline concern is resident memory after loading a very large Python dictionary.

Record at minimum:

- baseline RSS delta;
- candidate RSS delta;
- RSS saved/rate;
- cold load time;
- literal lookup throughput;
- generated lookup throughput;
- miss lookup throughput;
- generated lookup p50/p95/p99 latency.

Do not interpret the toy fixture's RSS numbers as production evidence.

---

## 13. Testing requirements

### Unit tests

Must cover:

- exact concat omission;
- exact membership and adversarial misses;
- OOV composable strings rejected;
- deterministic DAFSA serialization;
- deterministic asset serialization;
- ordered pronunciation variants;
- ambiguous composition remains literal;
- bounded search failure remains literal;
- no generated-word recipe structure;
- optimizer stays lossless;
- selector contains no expected pronunciation/word identity;
- German stress rule behavior;
- German linker behavior;
- serializer reload with no source access;
- JSON/TSV CLI round trips.

### Benchmark-harness tests

Must additionally cover:

- remote revisions/checksums are pinned;
- download URL contains immutable revision;
- cache path is revision scoped;
- downloader refuses network access without `--download`;
- complete toy `run -> save -> reload -> verify` path.

### Full-source gate

When `de_gold.json` is available, add/run a slow opt-in test asserting the canonical baseline size and exact verification. The supplied source experiment asserts 738,427 logical words.

Never silently skip the full test when a release is about to replace KokoroG2P's production resource. CI may skip it for ordinary PRs, but release validation must supply the data and run it.

---

## 14. Packaging and versioning

No `src/` layout.

`pyproject.toml` discovers `lexcompact*` from the repository root and excludes `benchmarks*` and `tests*` from the installed wheel.

Versioning is dynamic:

- `LEXCOMPACT_VERSION` environment variable wins for explicit reproducible builds;
- otherwise derive from Git `vX.Y.Z` tags;
- exact tag => `X.Y.Z`;
- commits after tag => PEP-440 post/local version;
- source archive without Git => documented development fallback.

Do not hard-code a release version in `pyproject.toml`.

The wheel must contain `lexcompact/py.typed`.

---

## 15. Performance priorities

Correctness hierarchy:

1. exact logical semantics;
2. no hidden per-generated-word table;
3. literal-entry reduction;
4. resident memory reduction;
5. generated lookup latency;
6. on-disk size.

Do not trade level 1 or 2 for any lower priority.

Potential future performance work that preserves the contract:

- binary DAFSA arrays instead of JSON serialization;
- binary/string-pool literal storage;
- memory-mapped membership and literal data;
- faster edge lookup than linear scanning per DAFSA state;
- compact prefix-index arrays;
- lazy decoding of pronunciation strings;
- rule-specific fast paths;
- shared segmentation cache bounded by size;
- profile-specific builders that discover additional global rules offline.

Any optimization that reintroduces one record per omitted word should be rejected as a regression in the primary representation goal, even if its bytes are small.

---

## 16. Research direction toward the <=400k German target

The inspected experiment remains at 586,889 literals, so approximately 186,889 additional literal removals are required to reach 400,000.

The supplied boundary/linker/selector report snapshots did not improve the 20.52% result. Treat those features as infrastructure and diagnostics, not proof that the target is solved.

Next research should use the offline failure-analysis tooling to answer:

- What proportion of retained words have alternate valid spellings/segmentations?
- How many mismatches are boundary-local and describable by a genuinely global rule?
- How many words become segmentable when useful atoms are promoted?
- Are there high-utility literal promotions that unlock large families?
- Can global phonological transforms recover exact variant tuples without word identity?
- Which candidate rules introduce conflicts on previously exact generated words?

Every proposed new rule must be evaluated by a complete rebuild and exact full-source verification. Aggregate support is not enough; one wrong pronunciation means the affected word must stay literal unless rule selection can distinguish it using shared runtime features.

Avoid morphologically appealing but unverified rules. The goal is not linguistic elegance; it is exact reconstruction under a compact shared runtime program.

---

## 17. Current MVP validation status

At creation time:

- the new KokoroG2P Codecrate pack reconstructed successfully with strict manifest/header checks;
- the source experiment's focused tests ran successfully: 14 passed, 1 skipped because `de_gold.json` was absent from the portable pack;
- this standalone repository's tests passed;
- the reproduced toy benchmark completed build, serialize, reload, independent verify, and fresh-process runtime measurement;
- toy German compound/boundary/linker mode reduced 9 logical words to 6 literals and reconstructed 3 implicitly with zero recipes and zero verification errors;
- network access from the execution sandbox was unavailable, so pinned remote downloads could not be exercised end-to-end there; downloader URL/cache/checksum/explicit-opt-in behavior is covered by local tests;
- the 738,427-word full benchmark was not rerun because its source JSON is not present in the supplied Codecrate snapshot.

Do not convert either of the last two environmental limitations into a claimed benchmark result.

---

## 18. Definition of done for KokoroG2P adoption

Before making the reduced asset the production German resource:

1. obtain the exact canonical `de_gold.json` used by the target KokoroG2P release;
2. run the standalone reducer with the intended profile/config;
3. save the `.lxc` asset;
4. start a fresh process and load only the `.lxc` asset;
5. run independent full-source verification for all 738,427 words plus adversarial misses;
6. run the anti-cheating audit;
7. run baseline/candidate fresh-process memory/load benchmarks;
8. run KokoroG2P's German unit/integration tests against the reduced loader;
9. compare end-to-end G2P output before/after on the existing German benchmark corpus;
10. package the reduced asset and verify wheel/sdist inclusion;
11. retain source provenance, builder configuration, source SHA-256, library version, and verification report as release artifacts;
12. only then remove the legacy full JSON from the production package.

The release criterion is **exact semantic parity plus measurable resident-entry/memory improvement**, not merely a smaller archive file.
