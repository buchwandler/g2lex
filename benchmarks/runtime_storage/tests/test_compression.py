from __future__ import annotations

from benchmarks.runtime_storage.compression import compare_compression_layers, compression_layers


def test_compression_layers_are_deterministic_and_named() -> None:
    data = ("Haus\thaus\n" * 20).encode()
    first = compression_layers(data)
    assert first == compression_layers(data)
    assert set(first) == {
        "plain_bytes",
        "gzip_bytes",
        "xz_bytes",
        "wheel_equivalent_deflate_bytes",
    }
    assert all(value > 0 for value in first.values())


def test_compression_comparison_reports_savings_for_repeated_data() -> None:
    baseline = ("Haus\thaus\n" * 100).encode()
    candidate = baseline[:20]
    result = compare_compression_layers(baseline, candidate)
    assert result["baseline_plain_bytes"] > result["candidate_plain_bytes"]
    assert result["net_plain_bytes_saved"] > 0
    assert result["reduction_vs_plain_pct"] > 0
    assert "net_gzip_bytes_saved" in result
    assert "net_xz_bytes_saved" in result
    assert "net_wheel_equivalent_deflate_bytes_saved" in result
