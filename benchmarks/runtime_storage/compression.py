"""Deterministic outer compression measurements for storage benchmarks."""

from __future__ import annotations

import gzip
import lzma
import zlib


def compression_layers(data: bytes) -> dict[str, int]:
    """Return byte sizes for archive layers used by source and wheel comparisons."""
    raw_deflate = zlib.compressobj(level=9, method=zlib.DEFLATED, wbits=-15)
    deflated = raw_deflate.compress(data) + raw_deflate.flush()
    return {
        "plain_bytes": len(data),
        "gzip_bytes": len(gzip.compress(data, mtime=0)),
        "xz_bytes": len(lzma.compress(data, format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC64)),
        "wheel_equivalent_deflate_bytes": len(deflated),
    }


def compare_compression_layers(baseline: bytes, candidate: bytes) -> dict[str, int | float]:
    """Compare candidate and baseline sizes at every deterministic outer layer."""
    baseline_sizes = compression_layers(baseline)
    candidate_sizes = compression_layers(candidate)
    result: dict[str, int | float] = {}
    for layer, baseline_size in baseline_sizes.items():
        candidate_size = candidate_sizes[layer]
        name = layer.removesuffix("_bytes")
        result[f"baseline_{layer}"] = baseline_size
        result[f"candidate_{layer}"] = candidate_size
        result[f"net_{name}_bytes_saved"] = baseline_size - candidate_size
        result[f"reduction_vs_{name}_pct"] = (
            (1 - candidate_size / baseline_size) * 100 if baseline_size else 0.0
        )
    return result


__all__ = ["compare_compression_layers", "compression_layers"]
