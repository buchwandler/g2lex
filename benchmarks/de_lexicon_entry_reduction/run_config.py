"""Execute every fully resolved benchmark case."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from lexcompact.asset import load
from lexcompact.audit import audit_runtime_representation

from .benchmark_memory import benchmark
from .config import load_config
from .run import run


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def _source_values(
    case: dict[str, Any], source_config: dict[str, Any]
) -> tuple[str, Path | None, Path | None]:
    source = case.get("source", source_config)
    if isinstance(source, str):
        source_id = source
        source_path = case.get("path", source_config.get("path"))
        data_root = case.get("data_root", source_config.get("data_root"))
    else:
        source_id = str(source.get("id", source_config.get("id", "builtin")))
        source_path = source.get("path", case.get("path", source_config.get("path")))
        data_root = source.get("data_root", case.get("data_root", source_config.get("data_root")))
    return (
        source_id,
        Path(source_path) if source_path else None,
        Path(data_root) if data_root else None,
    )


def run_config(
    config_path: str | Path, *, output: str | Path | None = None
) -> list[dict[str, object]]:
    config = load_config(config_path)
    root = Path(output or config.values["output"])
    source_config = config.values["source"]
    results: list[dict[str, object]] = []
    for case in config.values["cases"]:
        destination = root / str(case["name"])
        source_id, source_path, data_root = _source_values(case, source_config)
        limits = config.values["limits"]
        storage = case["storage"]
        methods = _merge(config.values.get("methods", {}), case.get("methods", {}))
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
            asset_format=str(storage.get("asset_format", "v3")),
            membership_backend=str(storage["membership_backend"]),
            literal_backend=str(storage["literal_backend"]),
            pronunciation_codec=str(storage["pronunciation_codec"]),
            seed=int(config.values["seed"]),
            methods=methods,
            config_sha256=str(case["effective_config_sha256"]),
        )
        asset = load(destination / "candidate.lxc")
        requested_membership = str(storage["membership_backend"])
        requested_literals = str(storage["literal_backend"])
        if getattr(asset.membership, "backend_id", "") != requested_membership:
            raise RuntimeError(
                f"loaded membership backend differs from requested {requested_membership!r}"
            )
        if getattr(asset.literals, "backend_id", "") != requested_literals:
            raise RuntimeError(
                f"loaded literal backend differs from requested {requested_literals!r}"
            )
        summary["config_sha256"] = config.sha256
        summary["case_config_sha256"] = case["effective_config_sha256"]
        summary["seed"] = int(config.values["seed"])
        summary["requested_membership_backend"] = requested_membership
        summary["requested_literal_backend"] = requested_literals
        summary["requested_pronunciation_codec"] = str(storage["pronunciation_codec"])
        (destination / "resolved-config.json").write_text(
            json.dumps(case, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        (destination / "audit.json").write_text(
            json.dumps(audit_runtime_representation(asset), indent=2) + "\n", encoding="utf-8"
        )
        (destination / "integration.json").write_text(
            json.dumps(
                {
                    "consumer": "mapping-compatible",
                    "source_id": source_id,
                    "status": "not-run",
                    "reason": "KokoroG2P consumer package is not part of the fixture run",
                    "phoneme_output_equality": None,
                    "fallback_behavior_equality": None,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (destination / "section-sizes.json").write_text(
            json.dumps(
                {
                    "asset_bytes": (destination / "candidate.lxc").stat().st_size,
                    "membership_bytes": asset.membership.serialized_bytes,
                    "literal_bytes": asset.literals.serialized_bytes,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (destination / "stage-coverage.json").write_text(
            json.dumps(
                {
                    "stages": summary.get("stage_coverage", {}),
                    "candidate_available_count_by_stage": {
                        stage: values.get("candidate_proposed", 0)
                        for stage, values in summary.get("stage_coverage", {}).items()
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        runtime_config = _merge(config.values["runtime"], case.get("runtime", {}))
        if bool(runtime_config.get("fresh_process", True)):
            runtime = benchmark(
                destination,
                source=source_id,
                data_root=data_root,
                path=source_path,
                sample_size=int(runtime_config["sample_size"]),
                repetitions=int(runtime_config["repetitions"]),
                seed=int(config.values["seed"]),
            )
            (destination / "runtime.json").write_text(
                json.dumps(runtime, indent=2) + "\n", encoding="utf-8"
            )
            summary["runtime"] = runtime
        (destination / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        results.append(summary)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(run_config(args.config, output=args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
