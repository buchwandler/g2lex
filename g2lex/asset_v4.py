"""V4 asset serialization built on the indexed binary container."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .composer import ImplicitComposer
from .container import V4Container
from .container import dumps as container_dumps
from .container import load as container_load
from .container import load_traversable as container_load_traversable
from .container import loads as container_loads
from .linkers import LinkerTable
from .literals import BinaryPoolLiteralStore
from .membership import BloomMembership, DafsaBinaryMembership, ExactMembership, MembershipIndex
from .model import ImplicitLexicon, LiteralLexicon, LiteralStore, SourceInfo
from .prefix_index import LiteralPrefixIndex
from .rules import RuleSet
from .runtime import RuntimeProgram
from .segmentation import SegmentationScorer
from .selectors import (
    GradientBoostedTreeSelector,
    HashedLogisticSelector,
    StaticPrioritySelector,
    TreePredicate,
    TreeSelector,
)

ASSET_FORMAT = "g2lex.asset.v4"
ASSET_SCHEMA = 4
LEGACY_ASSET_FORMATS = {(4, "lexcompact.asset.v4")}


def _json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _source_dict(source: SourceInfo) -> dict[str, Any]:
    result = asdict(source)
    result["path"] = Path(source.path).name if source.path else None
    return result


def manifest_dict(asset: ImplicitLexicon) -> dict[str, Any]:
    metrics = asset.metrics()
    return {
        "schema": ASSET_SCHEMA,
        "format": ASSET_FORMAT,
        "baseline_word_count": metrics.baseline_word_count,
        "literal_word_count": metrics.literal_word_count,
        "generated_word_count": metrics.generated_word_count,
        "per_generated_word_recipe_count": asset.per_generated_word_recipe_count,
        "membership_backend": getattr(asset.membership, "backend_id", "unknown"),
        "literal_backend": getattr(asset.literals, "backend_id", "unknown"),
        "runtime_program_version": "1",
        "runtime_stages": [
            getattr(item, "stage_id", "unknown")
            for item in getattr(asset.runtime_program, "reconstructors", ())
        ],
        "selector_kind": getattr(
            getattr(asset.runtime_program, "selector", None), "selector_id", "priority"
        ),
        "source": _source_dict(asset.source),
        "config_sha256": str(asset.metadata.get("config_sha256", "")),
        "source_sha256": asset.source.sha256,
    }


def asset_sections(asset: ImplicitLexicon) -> dict[str, bytes]:
    sections = {
        "composer.json": _json(
            {
                "max_components": asset.composer.max_components,
                "max_states": asset.composer.max_states,
                "two_part_fast_path": asset.composer.two_part_fast_path,
                "linkers": asset.composer.linkers.as_dict() if asset.composer.linkers else None,
                "recursive_components": asset.composer.recursive_components,
                "max_recursive_depth": asset.composer.max_recursive_depth,
                "segmentation_scorer": asset.composer.segmentation_scorer.as_dict()
                if asset.composer.segmentation_scorer
                else None,
                "metadata": asset.metadata,
            }
        ),
        "literal-index.json": _json(asset.literal_index.as_dict()),
        "manifest.json": _json(manifest_dict(asset)),
        "rules.json": _json(asset.composer.rules.as_dict()),
    }
    sections.update(asset.literals.serialize_sections())
    sections.update(asset.membership.serialize_sections())
    assert asset.runtime_program is not None
    if asset.runtime_program.legacy_composer is None:
        sections.update(asset.runtime_program.serialize_sections())
    return sections


def dumps(asset: ImplicitLexicon) -> bytes:
    return container_dumps(asset_sections(asset))


def save(path: str | Path, asset: ImplicitLexicon) -> None:
    Path(path).write_bytes(dumps(asset))


def _section(container: V4Container, name: str) -> bytes:
    try:
        return bytes(container[name])
    except KeyError as exc:
        raise ValueError(f"V4 asset is missing section {name!r}") from exc


def _selector_from_dict(value: dict[str, Any] | None):
    if not value:
        return StaticPrioritySelector()
    selector_id = str(value.get("selector_id", "static-priority"))
    if selector_id == "static-priority":
        return StaticPrioritySelector(tuple(value.get("order", StaticPrioritySelector().order)))
    if selector_id == "tree":
        predicates = tuple(
            TreePredicate(str(item[0]), str(item[1]), str(item[2]))
            for item in value.get("predicates", ())
        )
        return TreeSelector(
            predicates, tuple(value.get("default_order", StaticPrioritySelector().order))
        )
    if selector_id == "hashed-logistic":
        weights = tuple(
            (int(bucket), tuple((str(stage), int(weight)) for stage, weight in entries))
            for bucket, entries in value.get("weights", ())
        )
        return HashedLogisticSelector(weights, int(value.get("bucket_count", 1024)))
    if selector_id == "gbdt":
        return GradientBoostedTreeSelector(
            tuple((str(stage), int(score)) for stage, score in value.get("stage_scores", ()))
        )
    raise ValueError(f"unsupported serialized selector: {selector_id}")


def loads(data: bytes | bytearray | memoryview | V4Container) -> ImplicitLexicon:
    container = data if isinstance(data, V4Container) else container_loads(data)
    manifest = json.loads(_section(container, "manifest.json"))
    if (int(manifest.get("schema", -1)), manifest.get("format")) not in {
        (ASSET_SCHEMA, ASSET_FORMAT),
        *LEGACY_ASSET_FORMATS,
    }:
        raise ValueError("unsupported G2Lex reduction asset")
    source = SourceInfo(**manifest["source"])
    literals: LiteralStore
    if "literals.binary-pool" in container:
        literals = BinaryPoolLiteralStore.deserialize(_section(container, "literals.binary-pool"))
    else:
        literals = LiteralLexicon(json.loads(_section(container, "literals.json")))
    index = LiteralPrefixIndex.from_dict(json.loads(_section(container, "literal-index.json")))
    membership: ExactMembership
    if "membership.bloom" in container:
        if "membership.bloom-exact" not in container:
            raise ValueError("V4 Bloom membership is missing its exact backend")
        exact = DafsaBinaryMembership.deserialize(_section(container, "membership.bloom-exact"))
        membership = BloomMembership.deserialize(_section(container, "membership.bloom"), exact)
    elif "membership.dafsa-binary" in container:
        membership = DafsaBinaryMembership.deserialize(
            _section(container, "membership.dafsa-binary")
        )
    elif "membership.sorted-utf8" in container:
        from .membership import SortedUTF8Membership

        membership = SortedUTF8Membership.deserialize(_section(container, "membership.sorted-utf8"))
    else:
        membership = MembershipIndex.deserialize(_section(container, "membership.dafsa"))
    rules = RuleSet.from_dict(json.loads(_section(container, "rules.json")))
    config = json.loads(_section(container, "composer.json"))
    composer = ImplicitComposer(
        int(config.get("max_components", 4)),
        int(config.get("max_states", 100_000)),
        rules,
        bool(config.get("two_part_fast_path", True)),
        LinkerTable.from_dict(config["linkers"]) if config.get("linkers") else None,
        bool(config.get("recursive_components", False)),
        int(config.get("max_recursive_depth", 4)),
        SegmentationScorer.from_dict(config["segmentation_scorer"])
        if config.get("segmentation_scorer")
        else None,
    )
    metadata = dict(config.get("metadata", {}))
    metadata.setdefault("baseline_word_count", int(manifest["baseline_word_count"]))
    metadata.setdefault("per_generated_word_recipe_count", 0)
    runtime_program = None
    if "runtime-program.json" in container:
        runtime_config = json.loads(_section(container, "runtime-program.json"))
        runtime_program = RuntimeProgram.from_v4(
            composer,
            _selector_from_dict(runtime_config.get("selector")),
            stage_ids=tuple(
                str(item.get("stage_id"))
                for item in runtime_config.get("reconstructors", ())
                if item.get("stage_id")
            ),
        )
    asset = ImplicitLexicon(
        source, literals, index, membership, composer, metadata, runtime_program
    )
    if len(asset) != int(manifest["baseline_word_count"]):
        raise ValueError("V4 membership count does not match manifest")
    if len(literals) != int(manifest["literal_word_count"]):
        raise ValueError("V4 literal count does not match manifest")
    return asset


def load(path: str | Path) -> ImplicitLexicon:
    return loads(container_load(path))


def load_traversable(resource: Any) -> ImplicitLexicon:
    return loads(container_load_traversable(resource))


__all__ = [
    "ASSET_FORMAT",
    "ASSET_SCHEMA",
    "asset_sections",
    "dumps",
    "load",
    "load_traversable",
    "loads",
    "manifest_dict",
    "save",
]
