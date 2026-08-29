"""The stable ``pack`` command."""

from __future__ import annotations

import json
from argparse import Namespace

from ..operations import pack_file


def _cmd_pack(args: Namespace) -> int:
    metadata = {
        key: value
        for key, value in {
            "source_id": args.source_id,
            "display_name": args.display_name,
            "language": args.language,
            "locale": args.locale,
            "dialect": args.dialect,
            "tier": args.tier,
            "provider": args.provider,
            "revision": args.revision,
            "source_url": args.source_url,
            "pronunciation_alphabet": args.pronunciation_alphabet,
            "pronunciation_separator": args.pronunciation_separator,
            "role_namespace": args.role_namespace,
            "license_expression": args.license_expression,
            "license_name": args.license_name,
            "license_url": args.license_url,
            "attribution": args.attribution,
            "generator": args.generator,
            "parser_id": args.parser_id,
            "parser_version": args.parser_version,
        }.items()
        if value is not None
    }
    summary = pack_file(
        args.source,
        args.output,
        input_format=args.format,
        source_id=args.source_id,
        metadata=metadata,
        record_block_entries=args.record_block_entries,
        key_block_entries=args.key_block_entries,
        compression=args.compression,
        compression_level=args.compression_level,
    )
    if args.report:
        args.report.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0
