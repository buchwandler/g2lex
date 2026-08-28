"""Aggregate benchmark case summaries into leaderboard and Pareto reports."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def _load(root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(root.glob("*/summary.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        value["case"] = path.parent.name
        runtime = value.get("runtime", {})
        value["load_ms_median"] = runtime.get("candidate_load_ms_median")
        value["rss_after_load"] = (runtime.get("candidate_memory") or {}).get("VmRSS")
        value["pss_after_load"] = (runtime.get("candidate_memory") or {}).get("Pss")
        value["literal_qps"] = runtime.get("literal_lookup_words_per_second")
        value["baseline_rss_delta_bytes"] = runtime.get("baseline_rss_delta_bytes")
        value["candidate_rss_delta_bytes"] = runtime.get("candidate_rss_delta_bytes")
        value["rss_saved_bytes"] = runtime.get("rss_saved_bytes")
        value["rss_saved_rate"] = runtime.get("rss_saved_rate")
        value["baseline_pss_delta_bytes"] = runtime.get("baseline_pss_delta_bytes")
        value["candidate_pss_delta_bytes"] = runtime.get("candidate_pss_delta_bytes")
        value["pss_saved_bytes"] = runtime.get("pss_saved_bytes")
        value["pss_saved_rate"] = runtime.get("pss_saved_rate")
        value["generated_qps"] = runtime.get("generated_lookup_words_per_second")
        value["miss_qps"] = runtime.get("miss_lookup_words_per_second")
        value["generated_p50_ms"] = runtime.get("generated_lookup_p50_ms")
        value["generated_p95_ms"] = runtime.get("generated_lookup_p95_ms")
        value["generated_p99_ms"] = runtime.get("generated_lookup_p99_ms")
        value["build_seconds"] = (value.get("phases") or {}).get("candidate_build_seconds")
        value["runtime_model_bytes"] = (value.get("audit") or {}).get("runtime_model_bytes")
        rows.append(value)
    return rows


def _dominates(left: dict[str, Any], right: dict[str, Any]) -> bool:
    metrics = (
        ("literal_word_count", True),
        ("asset_bytes", True),
        ("load_ms_median", True),
        ("rss_after_load", True),
        ("generated_p95_ms", True),
    )
    comparable = [
        (left.get(key), right.get(key), lower)
        for key, lower in metrics
        if left.get(key) is not None and right.get(key) is not None
    ]
    if not comparable:
        return False
    no_worse = all(a <= b if lower else a >= b for a, b, lower in comparable)
    better = any(a < b if lower else a > b for a, b, lower in comparable)
    return no_worse and better


def aggregate(root: str | Path) -> dict[str, Any]:
    destination = Path(root)
    rows = _load(destination)
    rows.sort(
        key=lambda item: (
            not bool(item.get("lossless", False)),
            item.get("literal_word_count", 10**18),
            item.get("asset_bytes", 10**18),
        )
    )
    comparable_rows = [row for row in rows if row.get("lossless")] or rows
    pareto = [
        row
        for row in comparable_rows
        if not any(_dominates(other, row) for other in comparable_rows if other is not row)
    ]
    fields = (
        "case",
        "source_id",
        "source_physical_rows",
        "source_logical_word_count",
        "source_ordered_variant_count",
        "lossless",
        "baseline_word_count",
        "literal_word_count",
        "generated_word_count",
        "entry_reduction_rate",
        "asset_bytes",
        "membership_serialized_bytes",
        "load_ms_median",
        "rss_after_load",
        "pss_after_load",
        "baseline_rss_delta_bytes",
        "candidate_rss_delta_bytes",
        "rss_saved_bytes",
        "rss_saved_rate",
        "baseline_pss_delta_bytes",
        "candidate_pss_delta_bytes",
        "pss_saved_bytes",
        "pss_saved_rate",
        "literal_qps",
        "generated_qps",
        "miss_qps",
        "generated_p50_ms",
        "generated_p95_ms",
        "generated_p99_ms",
        "build_seconds",
        "runtime_model_bytes",
    )
    leaderboard = [{field: row.get(field) for field in fields} for row in rows]
    (destination / "leaderboard.json").write_text(
        json.dumps(leaderboard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (destination / "leaderboard.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(leaderboard)
    lines = ["# G2Lex benchmark leaderboard", "", "\t".join(fields)]
    lines.extend("\t".join(str(row.get(field, "")) for field in fields) for row in leaderboard)
    (destination / "leaderboard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (destination / "pareto.json").write_text(
        json.dumps(
            [{field: row.get(field) for field in fields} for row in pareto],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "cases": len(rows),
        "leaderboard": leaderboard,
        "pareto": [{field: row.get(field) for field in fields} for row in pareto],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(aggregate(args.root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
