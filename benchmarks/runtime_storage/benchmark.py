"""Compare dictionary, SQLite, and G2Lex lookup runtimes on a local source."""

from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
import time
import tracemalloc
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from statistics import quantiles

from g2lex import open as open_g2lex
from g2lex import pack_file, read_typed_lexicon

from .compression import compare_compression_layers


def _percentiles(values: list[float]) -> dict[str, float]:
    if len(values) < 2:
        value = values[0] if values else 0.0
        return {"p50": value, "p95": value, "p99": value}
    points = quantiles(values, n=100, method="inclusive")
    return {"p50": points[49], "p95": points[94], "p99": points[98]}


def _measure(
    name: str,
    opener: Callable[[], object],
    lookup: Callable[[object, str], object],
    iterate: Callable[[object], Iterable[str]],
    words: list[str],
    source_bytes: int,
    compiled_bytes: int,
    repetitions: int,
) -> dict[str, object]:
    started = time.perf_counter()
    tracemalloc.start()
    handle = opener()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    open_seconds = time.perf_counter() - started

    timings = []
    for index in range(repetitions):
        word = words[index % len(words)]
        started = time.perf_counter()
        lookup(handle, word)
        timings.append(time.perf_counter() - started)
    started = time.perf_counter()
    count = sum(1 for _ in iterate(handle))
    iteration_seconds = time.perf_counter() - started
    close = getattr(handle, "close", None)
    if close is not None:
        close()
    return {
        "case": name,
        "source_bytes": source_bytes,
        "compiled_bytes": compiled_bytes,
        "cold_open_seconds": open_seconds,
        "heap_current_bytes": current,
        "heap_peak_bytes": peak,
        "lookup_seconds": _percentiles(timings),
        "iteration_entries": count,
        "iteration_entries_per_second": count / iteration_seconds if iteration_seconds else 0.0,
    }


def run_benchmark(
    source: str | Path,
    *,
    input_format: str = "auto",
    repetitions: int = 1000,
) -> list[dict[str, object]]:
    """Run deterministic local storage cases and return JSON-compatible metrics."""
    source_path = Path(source)
    parsed = read_typed_lexicon(source_path, format=input_format)
    words = sorted(parsed.entries)
    if not words:
        raise ValueError("benchmark source must contain at least one word")
    with tempfile.TemporaryDirectory(prefix="g2lex-benchmark-") as directory:
        root = Path(directory)
        json_path = root / "source.json"
        json_path.write_text(
            json.dumps(parsed.entries, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )
        tsv_path = root / "source.tsv"
        tsv_path.write_text(
            "".join(f"{word}\t{value}\n" for word in words for value in parsed.entries[word]),
            encoding="utf-8",
        )
        asset_path = root / "source.g2lex"
        pack_file(source_path, asset_path, input_format=input_format)
        sqlite_path = root / "source.sqlite"
        with sqlite3.connect(sqlite_path) as connection:
            connection.execute("CREATE TABLE lexicon (word TEXT PRIMARY KEY, pronunciation TEXT)")
            connection.executemany(
                "INSERT INTO lexicon VALUES (?, ?)",
                [(word, parsed.entries[word][0]) for word in words],
            )
            connection.commit()

        def open_json() -> Mapping[str, object]:
            return json.loads(json_path.read_text(encoding="utf-8"))

        def open_tsv() -> Mapping[str, object]:
            return read_typed_lexicon(tsv_path, format="tsv").entries

        def open_sqlite() -> sqlite3.Connection:
            return sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)

        def lookup_sqlite(connection: sqlite3.Connection, word: str) -> object:
            return connection.execute(
                "SELECT pronunciation FROM lexicon WHERE word = ?", (word,)
            ).fetchone()

        def iterate_sqlite(connection: sqlite3.Connection) -> Iterable[str]:
            return (row[0] for row in connection.execute("SELECT word FROM lexicon ORDER BY word"))

        def open_g2lex_asset():
            return open_g2lex(asset_path)

        results = [
            _measure(
                "json-dict",
                open_json,
                lambda mapping, word: mapping.get(word),
                lambda mapping: mapping,
                words,
                json_path.stat().st_size,
                asset_path.stat().st_size,
                repetitions,
            ),
            _measure(
                "tsv-dict",
                open_tsv,
                lambda mapping, word: mapping.get(word),
                lambda mapping: mapping,
                words,
                tsv_path.stat().st_size,
                asset_path.stat().st_size,
                repetitions,
            ),
            _measure(
                "sqlite",
                open_sqlite,
                lookup_sqlite,
                iterate_sqlite,
                words,
                sqlite_path.stat().st_size,
                asset_path.stat().st_size,
                repetitions,
            ),
            _measure(
                "g2lex",
                open_g2lex_asset,
                lambda lexicon, word: lexicon.get(word),
                lambda lexicon: lexicon,
                words,
                source_path.stat().st_size,
                asset_path.stat().st_size,
                repetitions,
            ),
        ]
        baselines = (
            json_path.read_bytes(),
            tsv_path.read_bytes(),
            sqlite_path.read_bytes(),
            source_path.read_bytes(),
        )
        asset_data = asset_path.read_bytes()
        for result, baseline in zip(results, baselines, strict=True):
            result["compression"] = compare_compression_layers(baseline, asset_data)
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--format", default="auto")
    parser.add_argument("--repetitions", type=int, default=1000)
    args = parser.parse_args()
    print(
        json.dumps(
            run_benchmark(args.source, input_format=args.format, repetitions=args.repetitions),
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
