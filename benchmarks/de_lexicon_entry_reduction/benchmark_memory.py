#!/usr/bin/env python3
"""Measure fresh-process load, resident memory, and lookup costs."""
from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable


def _snapshot() -> dict[str, int | None]:
    values: dict[str, int | None] = {"VmRSS": None, "VmHWM": None, "Rss": None, "Pss": None, "Private_Clean": None, "Private_Dirty": None, "Shared_Clean": None, "Shared_Dirty": None}
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            key, _, value = line.partition(":")
            if key in {"VmRSS", "VmHWM"}:
                values[key] = int(value.strip().split()[0]) * 1024
    except FileNotFoundError:
        pass
    try:
        for line in Path("/proc/self/smaps_rollup").read_text().splitlines():
            key, _, value = line.partition(":")
            if key in values:
                values[key] = int(value.strip().split()[0]) * 1024
    except FileNotFoundError:
        pass
    return values


def _faults() -> dict[str, int]:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return {"major": int(usage.ru_majflt), "minor": int(usage.ru_minflt), "maxrss": int(usage.ru_maxrss * (1 if platform.system() == "Darwin" else 1024))}


def _diff(after: dict[str, int | None], before: dict[str, int | None]) -> dict[str, int | None]:
    return {key: (after[key] - before[key] if after[key] is not None and before[key] is not None else after[key]) for key in after}


def _worker(kind: str, run: Path, source: str, data_root: Path | None, path: Path | None) -> None:
    before = _snapshot()
    faults_before = _faults()
    started = time.perf_counter()
    if kind == "candidate":
        from lexcompact.asset import load
        candidate = load(run / "candidate.lxc")
        count = candidate.membership.word_count
    else:
        from .sources import load_source
        loaded = load_source(source, data_root=data_root, path=path)
        count = len(loaded.entries)
    after = _snapshot()
    faults_after = _faults()
    print(json.dumps({
        "process_start": before,
        "post_load": after,
        "memory_delta": _diff(after, before),
        "page_faults": {key: faults_after[key] - faults_before[key] for key in ("major", "minor")},
        "ru_maxrss": faults_after["maxrss"],
        "load_ms": (time.perf_counter() - started) * 1000,
        "word_count": count,
        "measurement": "fresh-process-os-warm",
    }))


def _stratified(values: Iterable[str], size: int, seed: int) -> tuple[str, ...]:
    ordered = sorted(values)
    if len(ordered) <= size:
        return tuple(ordered)
    buckets: dict[int, list[str]] = {}
    for value in ordered:
        buckets.setdefault(min(len(value) // 4, 12), []).append(value)
    result: list[str] = []
    for bucket in sorted(buckets):
        group = buckets[bucket]
        take = max(1, round(size * len(group) / len(ordered)))
        if take >= len(group):
            result.extend(group)
        else:
            stride = len(group) / take
            result.extend(group[min(len(group) - 1, int(index * stride + (seed % 3) / 3))] for index in range(take))
    return tuple(dict.fromkeys(result))[:size]


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    return sorted(values)[min(len(values) - 1, max(0, (len(values) * percentile + 99) // 100 - 1))]


def _lookup_metrics(run: Path, sample_size: int, seed: int) -> dict[str, object]:
    from lexcompact.asset import load
    from lexcompact.verify import adversarial_misses
    candidate = load(run / "candidate.lxc")
    all_words = tuple(candidate.membership.iter_words())
    literal_words = tuple(candidate.literals)
    generated = tuple(word for word in all_words if word not in candidate.literals)
    categories = {"literal": literal_words, "generated": generated, "miss": adversarial_misses(all_words)}
    metrics: dict[str, object] = {"sample_size_requested": sample_size, "sample_counts": {}}
    for name, words in categories.items():
        sample = _stratified(words, sample_size, seed)
        durations: list[float] = []
        started = time.perf_counter()
        for word in sample:
            one = time.perf_counter_ns()
            candidate.lookup_all(word)
            durations.append((time.perf_counter_ns() - one) / 1_000_000)
        elapsed = time.perf_counter() - started
        metrics["sample_counts"][name] = len(sample)
        metrics[f"{name}_lookup_words_per_second"] = len(sample) / elapsed if elapsed else 0.0
        if durations:
            metrics[f"{name}_lookup_p50_ms"] = _percentile(durations, 50)
            metrics[f"{name}_lookup_p95_ms"] = _percentile(durations, 95)
            metrics[f"{name}_lookup_p99_ms"] = _percentile(durations, 99)
            metrics[f"{name}_lookup_max_ms"] = max(durations)
    return metrics


def _run_worker(kind: str, run: Path, source: str, data_root: Path | None, path: Path | None) -> dict[str, object]:
    command = [sys.executable, "-m", "benchmarks.de_lexicon_entry_reduction.benchmark_memory", "--worker", kind, "--run", str(run), "--source", source]
    if data_root:
        command.extend(("--data-root", str(data_root)))
    if path:
        command.extend(("--path", str(path)))
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def benchmark(run: Path, *, source: str = "builtin", data_root: Path | None = None, path: Path | None = None, sample_size: int = 1000, repetitions: int = 3, seed: int = 0) -> dict[str, object]:
    if sample_size < 1 or repetitions < 1:
        raise ValueError("sample_size and repetitions must be positive")
    baseline_runs = [_run_worker("baseline", run, source, data_root, path) for _ in range(repetitions)]
    candidate_runs = [_run_worker("candidate", run, source, data_root, path) for _ in range(repetitions)]
    lookup = _lookup_metrics(run, sample_size, seed)
    baseline_loads = [float(item["load_ms"]) for item in baseline_runs]
    candidate_loads = [float(item["load_ms"]) for item in candidate_runs]
    candidate_memory = candidate_runs[-1]["post_load"]
    return {
        "baseline_load_ms_median": statistics.median(baseline_loads),
        "candidate_load_ms_median": statistics.median(candidate_loads),
        "baseline_memory": baseline_runs[-1]["post_load"],
        "candidate_memory": candidate_memory,
        "candidate_memory_delta": candidate_runs[-1]["memory_delta"],
        "candidate_page_faults": candidate_runs[-1]["page_faults"],
        "candidate_ru_maxrss": candidate_runs[-1]["ru_maxrss"],
        "repetitions": repetitions,
        "runtime_repetitions": {"baseline": baseline_runs, "candidate": candidate_runs},
        "mapped_file_bytes": (run / "candidate.lxc").stat().st_size,
        **lookup,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--source", default="builtin")
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--path", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", choices=("baseline", "candidate"))
    parser.add_argument("--sample-size", type=int, default=1000)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    if args.worker:
        _worker(args.worker, args.run, args.source, args.data_root, args.path)
        return 0
    result = benchmark(args.run, source=args.source, data_root=args.data_root, path=args.path, sample_size=args.sample_size, repetitions=args.repetitions, seed=args.seed)
    destination = args.output or args.run / "runtime.json"
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
