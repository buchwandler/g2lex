"""Manifest-driven sources reproduced from the KokoroG2P experiment."""

from __future__ import annotations

import hashlib
import importlib.resources
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

from lexcompact.io import parse_json_bytes, parse_tsv_bytes
from lexcompact.model import LexiconData, SourceInfo

ROOT = Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "source_manifest.toml"


@dataclass(frozen=True, slots=True)
class SourceSpec:
    source_id: str
    values: dict[str, Any]
    parser_version: str = "1"
    view_version: str = "1"

    @property
    def kind(self) -> str:
        return str(self.values.get("kind", ""))

    @property
    def revision(self) -> str | None:
        value = self.values.get("revision")
        return str(value) if value is not None else None

    @property
    def filename(self) -> str | None:
        value = self.values.get("filename")
        return str(value) if value is not None else None

    def source_info(self, *, path: Path | None = None, sha256: str = "", size_bytes: int | None = None) -> SourceInfo:
        return SourceInfo(
            self.source_id,
            self.revision,
            sha256 or str(self.values.get("sha256", "")),
            str(self.values.get("license", "")),
            str(self.values.get("provenance_status", "")),
            self.parser_version,
            self.view_version,
            str(self.values.get("format", "")),
            str(path) if path else None,
            size_bytes if size_bytes is not None else self.values.get("size_bytes"),
        )


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, SourceSpec]:
    with path.open("rb") as handle:
        document = tomllib.load(handle)
    fmt = document.get("format", {})
    return {
        source_id: SourceSpec(
            source_id,
            dict(values),
            str(fmt.get("parser_version", "1")),
            str(fmt.get("view_version", "1")),
        )
        for source_id, values in document.get("sources", {}).items()
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_source_path(spec: SourceSpec, data_root: Path | None = None, path: Path | None = None) -> Path | None:
    if path is not None:
        return path
    if spec.kind == "package_json":
        return None
    if spec.kind == "local_file" and spec.filename is not None and data_root is None:
        return ROOT / spec.filename
    if data_root is None or spec.filename is None:
        return None
    candidates = (
        data_root / spec.filename,
        data_root / spec.source_id / (spec.revision or "") / spec.filename,
        data_root / (spec.revision or "") / spec.filename,
    )
    return next((candidate for candidate in candidates if candidate.is_file()), candidates[0])


def _with_source(parsed: LexiconData, source: SourceInfo) -> LexiconData:
    return LexiconData(parsed.entries, source, parsed.physical_rows, dict(parsed.metadata)).runtime_unique()


def load_source(source_id: str, *, data_root: Path | None = None, path: Path | None = None, manifest_path: Path = MANIFEST_PATH) -> LexiconData:
    specs = load_manifest(manifest_path)
    try:
        spec = specs[source_id]
    except KeyError as exc:
        raise ValueError(f"Unknown lexicon source: {source_id}") from exc
    if spec.kind == "package_json":
        package = str(spec.values["resource_package"])
        name = str(spec.values["resource_name"])
        try:
            resource = importlib.resources.files(package).joinpath(name)
            data = resource.read_bytes()
        except (ModuleNotFoundError, FileNotFoundError) as exc:
            raise FileNotFoundError(
                "builtin source requires an installed/source checkout of kokorog2p "
                "containing kokorog2p/de/data/de_gold.json; alternatively pass --path"
            ) from exc
        parsed = parse_json_bytes(data, source_id=source_id)
        return _with_source(parsed, spec.source_info(size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    resolved = resolve_source_path(spec, data_root, path)
    if resolved is None or not resolved.is_file():
        raise FileNotFoundError(
            f"Source {source_id!r} is unavailable; provide --data-root or --path for {spec.filename}"
        )
    actual = sha256_file(resolved)
    expected = str(spec.values.get("sha256", ""))
    if expected and actual != expected:
        raise ValueError(f"Checksum mismatch for {resolved}: expected {expected}, got {actual}")
    data = resolved.read_bytes()
    parsed = parse_tsv_bytes(data, path=resolved, source_id=source_id)
    return _with_source(parsed, spec.source_info(path=resolved, sha256=actual, size_bytes=len(data)))
