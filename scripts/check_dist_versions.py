"""Validate that built g2lex distributions agree on one version."""

from __future__ import annotations

import argparse
import tarfile
import zipfile
from email.parser import Parser
from pathlib import Path


def _metadata_version(text: str, *, source: Path) -> str:
    metadata = Parser().parsestr(text, headersonly=True)
    name = metadata.get("Name")
    version = metadata.get("Version")
    if name != "g2lex" or not version:
        raise SystemExit(f"{source}: invalid g2lex distribution metadata")
    return version.strip()


def wheel_version(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(names) != 1:
            raise SystemExit(f"{path}: expected exactly one dist-info/METADATA")
        return _metadata_version(archive.read(names[0]).decode("utf-8"), source=path)


def sdist_version(path: Path) -> str:
    with tarfile.open(path, "r:gz") as archive:
        members = [
            member
            for member in archive.getmembers()
            if member.name.count("/") == 1 and member.name.endswith("/PKG-INFO")
        ]
        if len(members) != 1:
            raise SystemExit(f"{path}: expected exactly one top-level PKG-INFO")
        handle = archive.extractfile(members[0])
        if handle is None:
            raise SystemExit(f"{path}: unable to read PKG-INFO")
        return _metadata_version(handle.read().decode("utf-8"), source=path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist-dir", type=Path, default=Path("dist"))
    parser.add_argument("--expected-version")
    args = parser.parse_args()

    wheels = sorted(args.dist_dir.glob("g2lex-*.whl"))
    sdists = sorted(args.dist_dir.glob("g2lex-*.tar.gz"))
    artifacts = sorted(path for path in args.dist_dir.iterdir() if path.is_file())
    if len(wheels) != 1 or len(sdists) != 1:
        raise SystemExit(
            f"{args.dist_dir}: expected exactly one wheel and one sdist; "
            f"found {len(wheels)} wheel(s), {len(sdists)} sdist(s)"
        )
    expected_artifacts = sorted([wheels[0], sdists[0]])
    if artifacts != expected_artifacts:
        names = ", ".join(path.name for path in artifacts)
        raise SystemExit(f"{args.dist_dir}: unexpected distribution artifacts: {names}")

    wheel = wheel_version(wheels[0])
    sdist = sdist_version(sdists[0])
    if wheel != sdist:
        raise SystemExit(f"distribution version mismatch: wheel={wheel}, sdist={sdist}")
    if args.expected_version and wheel != args.expected_version:
        raise SystemExit(
            f"release version mismatch: expected={args.expected_version}, built={wheel}"
        )
    print(f"validated g2lex distribution version: {wheel}")


if __name__ == "__main__":
    main()
