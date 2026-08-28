"""High-level G2Lex v1 packing, export, and comparison operations."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .format import pack_typed
from .io import read_typed_lexicon
from .lexicon import Lexicon, open_lexicon
from .value import WORD_ONLY, TaggedValue, as_plain_selector, as_plain_value
from .verify_exact import verify_typed


def pack_file(
    source: str | Path,
    output: str | Path,
    *,
    input_format: str = "auto",
    source_id: str | None = None,
    metadata: Mapping[str, object] | None = None,
    record_block_entries: int = 256,
    key_block_entries: int = 32,
    compression: str = "zlib",
    compression_level: int = 9,
) -> dict[str, object]:
    parsed = read_typed_lexicon(source, format=input_format, source_id=source_id)
    packed = pack_typed(
        parsed,
        metadata=metadata,
        record_block_entries=record_block_entries,
        key_block_entries=key_block_entries,
        compression=compression,
        compression_level=compression_level,
    )
    from .lexicon import open_bytes

    candidate = open_bytes(packed)
    try:
        verification = verify_typed(candidate, parsed.entries)
    finally:
        candidate.close()
    if not verification["lossless"]:
        raise ValueError(f"G2Lex v1 self-verification failed: {verification}")
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(packed)
        os.replace(temporary, destination)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    return {
        "source_entry_count": len(parsed),
        "asset_entry_count": len(parsed),
        "asset_bytes": len(packed),
        "logical_sha256": parsed.logical_sha256,
        "source_sha256": parsed.source.sha256,
        "self_verified": True,
    }


def _entries(asset: Lexicon | Mapping[str, Any]) -> Mapping[str, Any]:
    return asset


def _json_value(value: Any) -> object:
    if value is WORD_ONLY:
        raise ValueError("word-only entries cannot be represented in JSON maps")
    return as_plain_value(value)


def _write_json(path: Path, entries: Mapping[str, Any]) -> None:
    payload = {word: _json_value(value) for word, value in entries.items()}
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def _write_jsonl(path: Path, entries: Mapping[str, Any]) -> None:
    lines: list[str] = []
    for word, value in entries.items():
        record: dict[str, Any]
        if value is WORD_ONLY:
            record = {"word": word, "kind": "word"}
        elif isinstance(value, TaggedValue):
            record = {
                "word": word,
                "kind": "tagged",
                "items": [[tag, as_plain_selector(item)] for tag, item in value.items],
            }
        elif isinstance(value, str):
            record = {"word": word, "kind": "scalar", "value": value}
        else:
            record = {"word": word, "kind": "list", "value": list(value)}
        lines.append(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _write_tsv(
    path: Path, entries: Mapping[str, Any], *, extended: bool, allow_lossy: bool
) -> None:
    lines: list[str] = []
    for word, value in entries.items():
        if not extended:
            if value is WORD_ONLY or isinstance(value, TaggedValue):
                if not allow_lossy:
                    raise ValueError("legacy TSV cannot represent tagged or word-only values")
                continue
            values = (value,) if isinstance(value, str) else value
            lines.extend(f"{word}\t{item}\n" for item in values)
            continue
        if value is WORD_ONLY:
            lines.append(f"{word}\tword\t\t\n")
        elif isinstance(value, TaggedValue):
            for tag, item in value.items:
                encoded = json.dumps(
                    as_plain_selector(item), ensure_ascii=False, separators=(",", ":")
                )
                lines.append(f"{word}\ttagged\t{tag}\t{encoded}\n")
        elif isinstance(value, str):
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            lines.append(f"{word}\tscalar\t\t{encoded}\n")
        else:
            encoded = json.dumps(list(value), ensure_ascii=False, separators=(",", ":"))
            lines.append(f"{word}\tlist\t\t{encoded}\n")
    path.write_text("".join(lines), encoding="utf-8")


def export_file(
    asset: str | Path | Lexicon,
    output: str | Path,
    *,
    format: str = "auto",
    allow_lossy: bool = False,
) -> None:
    if isinstance(asset, (str, Path)):
        lexicon = open_lexicon(asset)
        owned = True
    else:
        lexicon = asset
        owned = False
    try:
        destination = Path(output)
        fmt = format
        if fmt == "auto":
            suffix = destination.suffix.lower()
            fmt = {".json": "kokoro-json", ".jsonl": "jsonl", ".txt": "words"}.get(suffix, "tsv")
        if fmt in {"json", "json-map", "kokoro-json"}:
            _write_json(destination, _entries(lexicon))
        elif fmt == "jsonl":
            _write_jsonl(destination, _entries(lexicon))
        elif fmt == "tsv":
            _write_tsv(destination, _entries(lexicon), extended=False, allow_lossy=allow_lossy)
        elif fmt == "lxc-tsv":
            _write_tsv(destination, _entries(lexicon), extended=True, allow_lossy=allow_lossy)
        elif fmt == "words":
            if any(value is not WORD_ONLY for value in lexicon.values()) and not allow_lossy:
                raise ValueError("words export requires membership-only values")
            destination.write_text("".join(f"{word}\n" for word in lexicon), encoding="utf-8")
        else:
            raise ValueError(f"unsupported export format: {format!r}")
    finally:
        if owned:
            lexicon.close()


def convert_file(
    source: str | Path,
    output: str | Path,
    *,
    input_format: str = "auto",
    output_format: str = "auto",
    allow_lossy: bool = False,
) -> None:
    source_path = Path(source)
    if source_path.read_bytes()[:4] == b"G2LX":
        export_file(source_path, output, format=output_format, allow_lossy=allow_lossy)
        return
    parsed = read_typed_lexicon(source_path, format=input_format)
    destination = Path(output)
    fmt = output_format
    if fmt == "auto":
        suffix = destination.suffix.lower()
        fmt = {".json": "kokoro-json", ".jsonl": "jsonl", ".txt": "words"}.get(suffix, "tsv")
    if fmt in {"json", "json-map", "kokoro-json"}:
        _write_json(destination, parsed.entries)
    elif fmt == "jsonl":
        _write_jsonl(destination, parsed.entries)
    elif fmt == "tsv":
        _write_tsv(destination, parsed.entries, extended=False, allow_lossy=allow_lossy)
    elif fmt == "lxc-tsv":
        _write_tsv(destination, parsed.entries, extended=True, allow_lossy=allow_lossy)
    elif fmt == "words":
        if any(value is not WORD_ONLY for value in parsed.entries.values()) and not allow_lossy:
            raise ValueError("words export requires membership-only values")
        destination.write_text("".join(f"{word}\n" for word in parsed.entries), encoding="utf-8")
    else:
        raise ValueError(f"unsupported conversion format: {output_format!r}")


def verify_file(
    source: str | Path, asset: str | Path, *, input_format: str = "auto"
) -> dict[str, object]:
    parsed = read_typed_lexicon(source, format=input_format)
    lexicon = open_lexicon(asset)
    try:
        return verify_typed(lexicon, parsed.entries)
    finally:
        lexicon.close()


def inspect_file(asset: str | Path) -> dict[str, object]:
    lexicon = open_lexicon(asset)
    try:
        manifest = lexicon.metadata
        return {
            "format": manifest.get("format"),
            "schema": manifest.get("schema"),
            "entry_count": len(lexicon),
            "source": manifest.get("source"),
            "logical_sha256": manifest.get("logical_sha256"),
            "file_bytes": Path(asset).stat().st_size,
            "key_index_bytes": len(lexicon._container.section_view("keys.fci")),
            "record_directory_bytes": len(lexicon._container.section_view("records.dir")),
            "record_blocks_bytes": len(lexicon._container.section_view("records.blocks")),
            "tag_count": len(lexicon._container.tags),
            "record_block_count": len(lexicon._container.record_descriptors),
        }
    finally:
        lexicon.close()
