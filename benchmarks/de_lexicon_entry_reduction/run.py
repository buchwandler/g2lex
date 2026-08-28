#!/usr/bin/env python3
"""Build and verify one KokoroG2P-compatible entry-reduction candidate."""
from __future__ import annotations
import argparse, csv, json
from pathlib import Path
from lexcompact.asset import load, save, runtime_asset_bytes
from lexcompact.builder import build_implicit_lexicon
from lexcompact.optimizer import optimize_basis
from lexcompact.profiles.german import german_linker_table, german_rules
from lexcompact.reports import report_markdown, summary_dict
from lexcompact.rules import default_rules
from lexcompact.selector import extract_features, train_selector
from lexcompact.segmentation import SegmentationScorer
from lexcompact.verify import verify_candidate
from .sources import load_source


def _train_v2_selector(source, base_build, rules):
    rows = []
    for failure in base_build.failures:
        components_value = failure.get("candidate_components")
        if not components_value:
            continue
        components = tuple(components_value)
        if any(component not in base_build.asset.literals for component in components):
            continue
        variants = tuple(base_build.asset.literals[component] for component in components)
        expected = source.lookup_all(str(failure["word"]))
        exact = [
            rule.rule_id
            for rule in rules.rules
            if rule.applies(str(failure["word"]), components, variants)
            and rule.compose(str(failure["word"]), components, variants) == expected
        ]
        target_rule = "C0" if "C0" in exact else str(failure.get("candidate_rule") or "C1")
        rows.append({"features": extract_features(str(failure["word"]), components, variants), "target_rule": target_rule})
    return train_selector(
        rows,
        default_rule="C1" if any(rule.rule_id == "C1" for rule in rules.rules) else "C0",
        min_support=100,
        max_leaves=64,
    )


def run(source_id: str, mode: str, output: Path, *, data_root: Path | None = None, path: Path | None = None,
        target_literals: int = 400_000, max_components: int = 4, max_states: int = 100_000,
        optimizer: str = "greedy", max_passes: int = 4, selector: str = "v1",
        boundary_rules: str = "v1", linkers: str = "v1",
        recursive_components: bool = False, max_recursive_depth: int = 4,
        segmentation_scorer: str = "v1") -> dict[str, object]:
    source = load_source(source_id, data_root=data_root, path=path)
    compound = mode == "implicit-compound"
    use_boundary = boundary_rules == "v2"
    linker_table = german_linker_table() if linkers == "german" else None
    if segmentation_scorer not in ("v1", "v2"):
        raise ValueError(f"unknown segmentation scorer: {segmentation_scorer}")
    scorer = SegmentationScorer() if segmentation_scorer == "v2" else None
    rules = german_rules(boundary_rules=use_boundary) if compound else default_rules(False)
    if selector == "v2":
        base_build = build_implicit_lexicon(
            source,
            rules=rules,
            max_components=max_components,
            max_states=max_states,
            linkers=linker_table,
            recursive_components=recursive_components,
            max_recursive_depth=max_recursive_depth,
            segmentation_scorer=scorer,
        )
        selector_model = _train_v2_selector(source, base_build, rules)
        rules = german_rules(boundary_rules=use_boundary, selector=selector_model) if compound else default_rules(False, selector=selector_model)
    elif selector != "v1":
        raise ValueError(f"unknown selector: {selector}")
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
    else:
        build = build_implicit_lexicon(
            source,
            rules=rules,
            max_components=max_components,
            max_states=max_states,
            linkers=linker_table,
            recursive_components=recursive_components,
            max_recursive_depth=max_recursive_depth,
            segmentation_scorer=scorer,
        )
    build.asset.metadata["target_literal_word_count"] = target_literals
    output.mkdir(parents=True, exist_ok=True)
    asset_path = output / "candidate.lxc"
    save(asset_path, build.asset)
    reloaded = load(asset_path)
    verification = verify_candidate(reloaded, source)
    summary = summary_dict(build, verification=verification, asset_bytes=runtime_asset_bytes(asset_path))
    summary.update({
        "mode": mode,
        "optimizer": optimizer,
        "selector": selector,
        "boundary_rules": boundary_rules,
        "linkers": linkers,
        "recursive_components": recursive_components,
        "max_recursive_depth": max_recursive_depth,
        "segmentation_scorer": segmentation_scorer,
    })
    (output / "verification.json").write_text(json.dumps(verification, indent=2) + "\n", encoding="utf-8")
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (output / "report.md").write_text(report_markdown(summary), encoding="utf-8")
    _write_failures(output / "literal_failures.tsv", build.failures)
    print(json.dumps(summary, indent=2))
    return summary


def _write_failures(path: Path, failures: list[dict[str, object]]) -> None:
    fields = ("word", "reason", "candidate", "candidate_components", "candidate_rule", "candidate_depth")
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
    parser.add_argument("--max-passes", type=int, default=4)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--path", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    run(args.source, args.mode, args.output, data_root=args.data_root, path=args.path,
        target_literals=args.target_literals, max_components=args.max_components,
        max_states=args.max_states, optimizer=args.optimizer, max_passes=args.max_passes,
        selector=args.selector, boundary_rules=args.boundary_rules, linkers=args.linkers,
        recursive_components=args.recursive_components,
        max_recursive_depth=args.max_recursive_depth,
        segmentation_scorer=args.segmentation_scorer)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
