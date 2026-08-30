from __future__ import annotations

from benchmarks.runtime_storage.compression import compression_layers
from g2lex.literals import BinaryPoolLiteralStore, InternedBinaryPoolLiteralStore


def test_interned_candidate_is_a_separate_benchmark_case() -> None:
    values = {str(index): ("shared pronunciation", "alternate") for index in range(10)}
    candidate = InternedBinaryPoolLiteralStore(values)
    baseline = BinaryPoolLiteralStore(values)
    assert candidate.backend_id == "interned-binary-pool-v1"
    assert candidate["0"] == values["0"]
    assert candidate.serialized_bytes > 0
    assert compression_layers(candidate.serialize())["plain_bytes"] == candidate.serialized_bytes
    assert baseline.backend_id == "binary-pool-v2"
