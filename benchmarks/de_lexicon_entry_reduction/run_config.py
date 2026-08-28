"""Run explicitly configured benchmark cases with resolved artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from lexcompact.audit import audit_runtime_representation
from lexcompact.asset import load

from .benchmark_memory import benchmark
from .config import load_config
from .run import run


def run_config(config_path: str | Path, *, output: str | Path | None = None) -> list[dict[str, object]]:
    config = load_config(config_path)
    root = Path(output or config.values["output"])
    source_config = config.values["source"]
    results: list[dict[str, object]] = []
    for case in config.values["cases"]:
        destination = root / str(case["name"])
        source_id = str(case.get("source", source_config.get("id", "builtin")))
        data_root = Path(case.get("data_root") or source_config.get("data_root")) if case.get("data_root") or source_config.get("data_root") else None
        source_path = Path(case.get("path") or source_config.get("path")) if case.get("path") or source_config.get("path") else None
        limits = config.values["limits"]
        summary = run(
            source_id,
            str(case.get("mode", "implicit-compound")),
            destination,
            data_root=data_root,
            path=source_path,
            target_literals=int(case.get("target_literals", limits["target_literals"])),
            max_components=int(case.get("max_components", limits["max_components"])),
            max_states=int(case.get("max_states", limits["max_states"])),
            optimizer=str(case.get("optimizer", "greedy")),
            selector=str(case.get("selector", "v1")),
            boundary_rules=str(case.get("boundary_rules", "v1")),
            linkers=str(case.get("linkers", "v1")),
            recursive_components=bool(case.get("recursive_components", False)),
            max_recursive_depth=int(case.get("max_recursive_depth", limits["max_recursive_depth"])),
            segmentation_scorer=str(case.get("segmentation_scorer", "v1")),
            asset_format=str(case.get("asset_format", config.values["storage"].get("asset_format", "v3"))),
        )
        asset = load(destination / "candidate.lxc")
        summary["config_sha256"] = config.sha256
        summary["seed"] = int(config.values["seed"])
        (destination / "resolved-config.json").write_text(json.dumps(config.values, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        (destination / "audit.json").write_text(json.dumps(audit_runtime_representation(asset), indent=2) + "\n", encoding="utf-8")
        (destination / "section-sizes.json").write_text(json.dumps({"asset_bytes": (destination / "candidate.lxc").stat().st_size, "membership_bytes": asset.membership.serialized_bytes, "literal_bytes": asset.literals.serialized_bytes}, indent=2) + "\n", encoding="utf-8")
        stage_counts: dict[str, int] = {}
        for failure in summary.get("literal_failures", []):
            stage = str(failure.get("candidate_rule") or "none")
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
        (destination / "stage-coverage.json").write_text(json.dumps({"candidate_available_count_by_stage": stage_counts}, indent=2) + "\n", encoding="utf-8")
        (destination / "training.json").write_text(json.dumps({"seed": config.values["seed"], "methods": config.values.get("methods", {})}, indent=2) + "\n", encoding="utf-8")
        (destination / "diagnostics").mkdir(exist_ok=True)
        if bool(config.values["runtime"].get("fresh_process", True)):
            runtime = benchmark(destination, source=source_id, data_root=data_root, path=source_path)
            (destination / "runtime.json").write_text(json.dumps(runtime, indent=2) + "\n", encoding="utf-8")
        (destination / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        results.append(summary)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    results = run_config(args.config, output=args.output)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
