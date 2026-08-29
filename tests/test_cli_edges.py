from __future__ import annotations

import json
from pathlib import Path

import pytest

from g2lex.cli import main
from g2lex.format import pack_typed


def _json_source(path: Path, values: object | None = None) -> None:
    path.write_text(
        json.dumps(values or {"a": "x", "tag": {"DEFAULT": "d", "ALT": None}}), encoding="utf-8"
    )


def test_cli_lookup_inspect_export_and_convert(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "source.json"
    _json_source(source)
    asset = tmp_path / "asset.g2lex"
    assert main(["pack", str(source), str(asset)]) == 0
    capsys.readouterr()

    assert main(["lookup", str(asset), "a"]) == 0
    assert json.loads(capsys.readouterr().out) == "x"
    assert main(["lookup", str(asset), "tag"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "kind": "tagged",
        "items": [["DEFAULT", "d"], ["ALT", None]],
    }
    assert main(["lookup", str(asset), "missing"]) == 1
    assert capsys.readouterr().out == ""

    assert main(["inspect", str(asset)]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["entry_count"] == 2 and inspected["format"] == "g2lex.lexicon.v1"

    exported = tmp_path / "export.jsonl"
    assert main(["export", str(asset), str(exported), "--format", "auto"]) == 0
    assert exported.read_text()
    converted = tmp_path / "converted.tsv"
    assert main(["convert", str(source), str(converted), "--format", "lxc-tsv"]) == 0
    assert "a\tscalar" in converted.read_text()


def test_cli_restore_diff_and_failure_exit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    left = tmp_path / "left.g2lex"
    right = tmp_path / "right.g2lex"
    left.write_bytes(pack_typed({"a": "x"}))
    right.write_bytes(pack_typed({"a": "x"}))
    assert main(["diff", str(left), str(right)]) == 0
    assert json.loads(capsys.readouterr().out)["same"] == 1
    right.write_bytes(pack_typed({"a": "different"}))
    assert main(["diff", str(left), str(right)]) == 0
    assert json.loads(capsys.readouterr().out)["different"] == 1

    restored = tmp_path / "restored.json"
    assert main(["restore", str(left), str(restored), "--format", "json"]) == 0
    assert json.loads(restored.read_text()) == {"a": "x"}
    assert main(["lookup", str(left), "missing"]) == 1
    assert capsys.readouterr().out == ""


def test_cli_argparse_rejects_invalid_profile_and_format(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    _json_source(source, {"a": "x"})
    with pytest.raises(SystemExit) as profile:
        main(["reduce", str(source), str(tmp_path / "out.lxc"), "--profile", "invalid"])
    assert profile.value.code == 2
    with pytest.raises(SystemExit) as fmt:
        main(["pack", str(source), str(tmp_path / "out"), "--format", "invalid"])
    assert fmt.value.code == 2


def test_cli_entrypoint_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as version:
        main(["--version"])
    assert version.value.code == 0
    assert "g2lex" in capsys.readouterr().out
