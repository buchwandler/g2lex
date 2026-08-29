"""Deterministic single-file runtime asset format."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

from .composer import ImplicitComposer
from .lexicon import Lexicon
from .linkers import LinkerTable
from .membership import MembershipIndex
from .model import ImplicitLexicon, LiteralLexicon, SourceInfo
from .prefix_index import LiteralPrefixIndex
from .rules import RuleSet
from .segmentation import SegmentationScorer

ASSET_FORMAT = "g2lex.asset.v3"
ASSET_SCHEMA = 3
LEGACY_ASSET_FORMATS = {(2, "lexcompact.asset.v2"), (3, "lexcompact.asset.v3")}
_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


LoadedAsset = Lexicon | ImplicitLexicon


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _source_dict(source: SourceInfo) -> dict[str, Any]:
    value = source.canonical_dict()
    value["path"] = Path(source.path).name if source.path else None
    return value


def manifest_dict(asset: ImplicitLexicon) -> dict[str, Any]:
    metrics = asset.metrics()
    target = int(str(asset.metadata.get("target_literal_word_count", 400_000)))
    return {
        "schema": ASSET_SCHEMA,
        "format": ASSET_FORMAT,
        "kind": "implicit-entry-reduction",
        "source": _source_dict(asset.source),
        "baseline_word_count": metrics.baseline_word_count,
        "literal_word_count": metrics.literal_word_count,
        "generated_word_count": metrics.generated_word_count,
        "entry_reduction_rate": metrics.entry_reduction_rate,
        "per_generated_word_recipe_count": asset.per_generated_word_recipe_count,
        "target_literal_word_count": target,
        "target_met": metrics.literal_word_count <= target,
        "composer_version": asset.metadata.get("composer_version", "1"),
        "membership_version": asset.metadata.get("membership_version", 1),
        "rule_version": asset.metadata.get("rule_version", "1"),
    }


def asset_members(asset: ImplicitLexicon) -> dict[str, bytes]:
    return {
        "manifest.json": _json_bytes(manifest_dict(asset)),
        "literals.json": _json_bytes({word: list(asset.literals[word]) for word in asset.literals}),
        "literal-index.json": _json_bytes(asset.literal_index.as_dict()),
        "membership.dafsa": asset.membership.serialize(),
        "rules.json": _json_bytes(asset.composer.rules.as_dict()),
        "composer.json": _json_bytes(
            {
                "max_components": asset.composer.max_components,
                "max_states": asset.composer.max_states,
                "two_part_fast_path": asset.composer.two_part_fast_path,
                "linkers": asset.composer.linkers.as_dict() if asset.composer.linkers else None,
                "recursive_components": asset.composer.recursive_components,
                "max_recursive_depth": asset.composer.max_recursive_depth,
                "segmentation_scorer": (
                    asset.composer.segmentation_scorer.as_dict()
                    if asset.composer.segmentation_scorer
                    else None
                ),
                "metadata": asset.metadata,
            }
        ),
    }


def dumps(asset: ImplicitLexicon) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in sorted(asset_members(asset).items()):
            info = zipfile.ZipInfo(name, _FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    return buffer.getvalue()


def save(path: str | Path, asset: ImplicitLexicon) -> None:
    Path(path).write_bytes(dumps(asset))


def loads(data: bytes) -> LoadedAsset:
    if data[:4] == b"G2LX":
        from .lexicon import open_bytes

        return open_bytes(data)
    if data[:4] == b"LXC4":
        from .asset_v4 import loads as loads_v4

        return loads_v4(data)
    with zipfile.ZipFile(io.BytesIO(data), "r") as archive:
        names = set(archive.namelist())
        required = {
            "manifest.json",
            "literals.json",
            "literal-index.json",
            "membership.dafsa",
            "rules.json",
            "composer.json",
        }
        missing = required - names
        if missing:
            raise ValueError(f"asset is missing members: {sorted(missing)}")
        manifest = json.loads(archive.read("manifest.json"))
        schema = int(manifest.get("schema", -1))
        asset_format = manifest.get("format")
        if (schema, asset_format) != (ASSET_SCHEMA, ASSET_FORMAT) and (
            schema,
            asset_format,
        ) not in LEGACY_ASSET_FORMATS:
            raise ValueError("unsupported G2Lex reduction asset")
        source = SourceInfo(**manifest["source"])
        literals = LiteralLexicon(json.loads(archive.read("literals.json")))
        index = LiteralPrefixIndex.from_dict(json.loads(archive.read("literal-index.json")))
        membership = MembershipIndex.deserialize(archive.read("membership.dafsa"))
        rules = RuleSet.from_dict(json.loads(archive.read("rules.json")))
        composer_config = json.loads(archive.read("composer.json"))
        composer = ImplicitComposer(
            int(composer_config.get("max_components", 4)),
            int(composer_config.get("max_states", 100_000)),
            rules,
            bool(composer_config.get("two_part_fast_path", True)),
            LinkerTable.from_dict(composer_config["linkers"])
            if composer_config.get("linkers")
            else None,
            bool(composer_config.get("recursive_components", False)),
            int(composer_config.get("max_recursive_depth", 4)),
            SegmentationScorer.from_dict(composer_config["segmentation_scorer"])
            if composer_config.get("segmentation_scorer")
            else None,
        )
        metadata = dict(composer_config.get("metadata", {}))
        metadata.setdefault("baseline_word_count", int(manifest["baseline_word_count"]))
        metadata.setdefault("per_generated_word_recipe_count", 0)
        candidate = ImplicitLexicon(source, literals, index, membership, composer, metadata)
        if len(literals) != int(manifest["literal_word_count"]):
            raise ValueError("asset literal count does not match manifest")
        if len(candidate) != int(manifest["baseline_word_count"]):
            raise ValueError("asset membership count does not match manifest")
        return candidate


def load(path: str | Path) -> LoadedAsset:
    path = Path(path)
    with path.open("rb") as handle:
        magic = handle.read(4)
        if magic == b"G2LX":
            from .lexicon import open_lexicon

            return open_lexicon(path)
        if magic == b"LXC4":
            from .asset_v4 import load as load_v4

            return load_v4(path)
    return loads(path.read_bytes())


def load_traversable(resource: Any) -> LoadedAsset:
    """Load from an importlib.resources Traversable or any object with read_bytes()."""
    data = resource.read_bytes()
    if data[:4] == b"G2LX":
        from .lexicon import open_traversable

        return open_traversable(resource)
    return loads(data)


def runtime_asset_bytes(path: str | Path) -> int:
    return Path(path).stat().st_size
