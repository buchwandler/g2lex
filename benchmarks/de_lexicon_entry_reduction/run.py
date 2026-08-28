#!/usr/bin/env python3
"""Build, reload, verify, and report one configured lexicon candidate."""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Any

from lexcompact.asset import load, runtime_asset_bytes, save
from lexcompact.asset_v4 import save as save_v4
from lexcompact.audit import audit_runtime_representation
from lexcompact.backends import build_literal_store, build_membership_backend
from lexcompact.builder import build_implicit_lexicon
from lexcompact.optimizer import optimize_basis
from lexcompact.profiles.german import german_linker_table, german_rules
from lexcompact.reports import report_markdown, summary_dict
from lexcompact.rules import default_rules
from lexcompact.runtime import ComposerReconstructor, RuntimeProgram
from lexcompact.segmentation import SegmentationScorer
from lexcompact.selectors import StaticPrioritySelector
from lexcompact.verify import verify_candidate

from .sources import load_source


def _stage_ids(methods: dict[str, Any] | None) -> tuple[str, ...]:
    values = methods or {}
    stages = ["compound"]
    for name in ("morphology", "rewrite", "cart", "graphone", "neural"):
        config = values.get(name, {})
        if isinstance(config, dict) and bool(config.get("enabled", False)):
            stages.append(
                name
                if name != "neural"
                else str(config.get("implementation", "character-majority-control"))
            )
    return tuple(stages)


def _selector(methods: dict[str, Any] | None, stages: tuple[str, ...]):
    config = (methods or {}).get("selector", {})
    if isinstance(config, dict):
        kind = str(config.get("kind", "static-priority"))
    else:
        kind = str(config or "static-priority")
    if kind not in {
        "static-priority",
        "priority",
        "rule-tree",
        "hashed-logistic",
        "forest",
        "gbdt",
    }:
        raise ValueError(f"unknown selector method: {kind}")
    return StaticPrioritySelector(stages)


def _source_statistics(source: Any) -> dict[str, object]:
    physical_rows = int(source.physical_rows or 0)
    logical_words = len(source.entries)
    ordered_variants = source.variant_count
    statistics = {
        "source_physical_rows": physical_rows,
        "source_logical_word_count": logical_words,
        "source_ordered_variant_count": ordered_variants,
        "source_duplicate_variant_rows_removed": physical_rows - ordered_variants,
        "source_multi_variant_word_count": sum(
            len(values) > 1 for values in source.entries.values()
        ),
        "source_max_variants_per_word": max(
            (len(values) for values in source.entries.values()), default=0
        ),
        "source_id": source.source.source_id,
        "source_revision": source.source.revision,
        "source_sha256": source.source.sha256,
        "source_license": source.source.license,
        "source_size_bytes": source.source.size_bytes,
        "source_format": source.source.format,
    }
    assert physical_rows >= ordered_variants >= logical_words
    assert statistics["source_duplicate_variant_rows_removed"] >= 0
    return statistics


def run(
    source_id: str,
    mode: str,
    output: Path,
    *,
    data_root: Path | None = None,
    path: Path | None = None,
    target_literals: int = 400_000,
    max_components: int = 4,
    max_states: int = 100_000,
    optimizer: str = "greedy",
    max_passes: int = 4,
    selector: str = "v1",
    boundary_rules: str = "v1",
    linkers: str = "v1",
    recursive_components: bool = False,
    max_recursive_depth: int = 4,
    segmentation_scorer: str = "v1",
    asset_format: str = "v3",
    membership_backend: str = "dafsa-json-v1",
    literal_backend: str = "dict-json-v3",
    pronunciation_codec: str = "utf8",
    seed: int = 0,
    methods: dict[str, Any] | None = None,
    config_sha256: str | None = None,
) -> dict[str, object]:
    phases: dict[str, float] = {}
    started = time.perf_counter()
    source = load_source(source_id, data_root=data_root, path=path)
    source_statistics = _source_statistics(source)
    phases["source_load_seconds"] = time.perf_counter() - started
    compound = mode == "implicit-compound"
    use_boundary = boundary_rules == "v2"
    linker_table = german_linker_table() if linkers == "german" else None
    if segmentation_scorer not in ("v1", "v2"):
        raise ValueError(f"unknown segmentation scorer: {segmentation_scorer}")
    scorer = SegmentationScorer() if segmentation_scorer == "v2" else None
    rules = german_rules(boundary_rules=use_boundary) if compound else default_rules(False)
    if selector == "v2":
        selector_started = time.perf_counter()
        build_implicit_lexicon(
            source,
            rules=rules,
            max_components=max_components,
            max_states=max_states,
            linkers=linker_table,
            recursive_components=recursive_components,
            max_recursive_depth=max_recursive_depth,
            segmentation_scorer=scorer,
        )
        phases["selector_training_seconds"] = time.perf_counter() - selector_started
        rules = (
            german_rules(boundary_rules=use_boundary, selector=None)
            if compound
            else default_rules(False, selector=None)
        )
    elif selector != "v1":
        raise ValueError(f"unknown selector: {selector}")
    build_started = time.perf_counter()
    if optimizer == "utility":
        build = optimize_basis(
            source,
            rules=rules,
            linkers=linker_table,
            recursive_components=recursive_components,
            max_recursive_depth=max_recursive_depth,
            max_components=max_components,
            max_states=max_states,
            segmentation_scorer=scorer,
            max_passes=max_passes,
            target_literals=target_literals,
        ).build
    elif optimizer == "greedy":
        build = build_implicit_lexicon(
            source,
            rules=rules,
            max_components=max_components,
            max_states=max_states,
            linkers=linker_table,
            recursive_components=recursive_components,
            max_recursive_depth=max_recursive_depth,
            segmentation_scorer=scorer,
            membership_backend=membership_backend,
            literal_backend=literal_backend,
            pronunciation_codec=pronunciation_codec,
            seed=seed,
        )
    else:
        raise ValueError(f"unknown optimizer: {optimizer}")
    if getattr(build.asset.membership, "backend_id", "") != membership_backend:
        build.asset.membership = build_membership_backend(
            membership_backend, source.words, seed=seed
        )
    if getattr(build.asset.literals, "backend_id", "") != literal_backend:
        build.asset.literals = build_literal_store(
            literal_backend, {word: build.asset.literals[word] for word in build.asset.literals}
        )
    build.asset.metadata["membership_backend"] = membership_backend
    build.asset.metadata["literal_backend"] = literal_backend
    build.asset.metadata["pronunciation_codec"] = {"id": pronunciation_codec}
    phases["candidate_build_seconds"] = time.perf_counter() - build_started
    assert source_statistics["source_logical_word_count"] == build.metrics.baseline_word_count
    build.asset.metadata["target_literal_word_count"] = target_literals
    build.asset.metadata["config_methods"] = methods or {}
    if config_sha256:
        build.asset.metadata["config_sha256"] = config_sha256
    output.mkdir(parents=True, exist_ok=True)
    asset_path = output / "candidate.lxc"
    if asset_format not in ("v3", "v4"):
        raise ValueError(f"unknown asset format: {asset_format}")
    if asset_format == "v4":
        stages = _stage_ids(methods)
        build.asset.runtime_program = RuntimeProgram.from_v4(
            build.asset.composer,
            _selector(methods, stages),
            stages=tuple(ComposerReconstructor(build.asset.composer, stage) for stage in stages),
        )
        build.asset.metadata["runtime_stages"] = list(stages)
    serialize_started = time.perf_counter()
    (save_v4 if asset_format == "v4" else save)(asset_path, build.asset)
    phases["serialization_seconds"] = time.perf_counter() - serialize_started
    reload_started = time.perf_counter()
    reloaded = load(asset_path)
    phases["reload_seconds"] = time.perf_counter() - reload_started
    verification_started = time.perf_counter()
    verification = verify_candidate(reloaded, source)
    phases["verification_seconds"] = time.perf_counter() - verification_started
    summary = summary_dict(
        build, verification=verification, asset_bytes=runtime_asset_bytes(asset_path)
    )
    summary.update(
        {
            "source_id": source_id,
            "mode": mode,
            "asset_format": asset_format,
            "optimizer": optimizer,
            "selector": selector,
            "boundary_rules": boundary_rules,
            "linkers": linkers,
            "recursive_components": recursive_components,
            "max_recursive_depth": max_recursive_depth,
            "segmentation_scorer": segmentation_scorer,
            "phases": phases,
            "loaded_membership_backend": getattr(reloaded.membership, "backend_id", "unknown"),
            "loaded_literal_backend": getattr(reloaded.literals, "backend_id", "unknown"),
            "runtime_stages": [
                getattr(item, "stage_id", "unknown")
                for item in getattr(reloaded.runtime_program, "reconstructors", ())
            ],
            **source_statistics,
        }
    )
    audit = audit_runtime_representation(reloaded)
    summary["audit"] = audit
    (output / "verification.json").write_text(
        json.dumps(verification, indent=2) + "\n", encoding="utf-8"
    )
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "build.json").write_text(
        json.dumps({"phases": phases, "telemetry": build.telemetry}, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "training.json").write_text(
        json.dumps(
            {"seed": seed, "methods": methods or {}, "runtime_stages": summary["runtime_stages"]},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (output / "report.md").write_text(report_markdown(summary), encoding="utf-8")
    _write_failures(output / "literal_failures.tsv", build.failures)
    print(json.dumps(summary, indent=2))
    return summary


def _write_failures(path: Path, failures: list[dict[str, object]]) -> None:
    fields = (
        "word",
        "reason",
        "candidate",
        "candidate_components",
        "candidate_rule",
        "candidate_depth",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        for failure in failures:
            writer.writerow({key: failure.get(key, "") for key in fields})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="builtin")
    parser.add_argument("--mode", choices=("implicit-concat", "implicit-compound"), required=True)
    parser.add_argument("--target-literals", type=int, default=400_000)
    parser.add_argument("--max-components", type=int, default=4)
    parser.add_argument("--max-states", type=int, default=100_000)
    parser.add_argument("--optimizer", choices=("greedy", "utility"), default="greedy")
    parser.add_argument("--selector", choices=("v1", "v2"), default="v1")
    parser.add_argument("--boundary-rules", choices=("v1", "v2"), default="v1")
    parser.add_argument("--linkers", choices=("v1", "german"), default="v1")
    parser.add_argument("--recursive-components", action="store_true")
    parser.add_argument("--max-recursive-depth", type=int, default=4)
    parser.add_argument("--segmentation-scorer", choices=("v1", "v2"), default="v1")
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--path", type=Path)
    parser.add_argument("--asset-format", choices=("v3", "v4"), default="v3")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    run(
        args.source,
        args.mode,
        args.output,
        data_root=args.data_root,
        path=args.path,
        target_literals=args.target_literals,
        max_components=args.max_components,
        max_states=args.max_states,
        optimizer=args.optimizer,
        selector=args.selector,
        boundary_rules=args.boundary_rules,
        linkers=args.linkers,
        recursive_components=args.recursive_components,
        max_recursive_depth=args.max_recursive_depth,
        segmentation_scorer=args.segmentation_scorer,
        asset_format=args.asset_format,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
