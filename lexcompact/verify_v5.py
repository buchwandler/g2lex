"""Verification and comparison of exact typed V5 lexicons."""

from __future__ import annotations

from collections.abc import Mapping

from .value import LexiconValue, logical_sha256


def _same_shape(left: object, right: object) -> bool:
    return type(left) is type(right)


def verify_typed(
    asset: Mapping[str, LexiconValue], source: Mapping[str, LexiconValue]
) -> dict[str, object]:
    """Compare every logical key and typed value in two mappings."""

    missing = extra = shape_mismatch = value_mismatch = 0
    tag_mismatch = null_mismatch = variant_order_mismatch = 0
    source_keys = set(source)
    asset_keys = set(asset)
    missing = len(source_keys - asset_keys)
    extra = len(asset_keys - source_keys)
    for word in source_keys & asset_keys:
        expected = source[word]
        actual = asset[word]
        if not _same_shape(expected, actual):
            shape_mismatch += 1
            continue
        if expected != actual:
            value_mismatch += 1
            if (
                isinstance(expected, tuple)
                and isinstance(actual, tuple)
                and set(expected) == set(actual)
            ):
                variant_order_mismatch += 1
            if hasattr(expected, "items") and hasattr(actual, "items"):
                expected_items = dict(expected.items)
                actual_items = dict(actual.items)
                if expected_items.keys() != actual_items.keys():
                    tag_mismatch += 1
                if any(
                    expected_items.get(tag) is None or actual_items.get(tag) is None
                    for tag in expected_items
                ):
                    null_mismatch += 1
    logical_sha_match = logical_sha256(source) == str(
        getattr(asset, "metadata", {}).get("logical_sha256", "")
    )
    logical_match = missing == extra == shape_mismatch == value_mismatch == 0 and logical_sha_match
    return {
        "lossless": logical_match,
        "source_entry_count": len(source),
        "asset_entry_count": len(asset),
        "missing": missing,
        "extra": extra,
        "shape_mismatch": shape_mismatch,
        "value_mismatch": value_mismatch,
        "tag_mismatch": tag_mismatch,
        "null_mismatch": null_mismatch,
        "variant_order_mismatch": variant_order_mismatch,
        "logical_sha256_match": logical_sha_match,
    }


class LexiconDiff:
    __slots__ = ("different", "only_a", "only_b", "same", "shape_different")

    def __init__(self, only_a: int, only_b: int, same: int, different: int, shape_different: int):
        self.only_a = only_a
        self.only_b = only_b
        self.same = same
        self.different = different
        self.shape_different = shape_different

    def as_dict(self) -> dict[str, int]:
        return {
            "only_a": self.only_a,
            "only_b": self.only_b,
            "same": self.same,
            "different": self.different,
            "shape_different": self.shape_different,
        }


def compare(a: Mapping[str, LexiconValue], b: Mapping[str, LexiconValue]) -> LexiconDiff:
    only_a = only_b = same = different = shape_different = 0
    a_iter, b_iter = iter(a), iter(b)
    left = next(a_iter, None)
    right = next(b_iter, None)
    while left is not None or right is not None:
        if right is None or (left is not None and left < right):
            only_a += 1
            left = next(a_iter, None)
        elif left is None or right < left:
            only_b += 1
            right = next(b_iter, None)
        else:
            left_value, right_value = a[left], b[right]
            if not _same_shape(left_value, right_value):
                shape_different += 1
                different += 1
            elif left_value == right_value:
                same += 1
            else:
                different += 1
            left = next(a_iter, None)
            right = next(b_iter, None)
    return LexiconDiff(only_a, only_b, same, different, shape_different)
