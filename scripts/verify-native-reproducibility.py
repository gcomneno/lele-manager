#!/usr/bin/env python3
"""Verify normalized reproducibility of native PyInstaller bundles."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts" / "build-native-app.py"
NATIVE_BUNDLE = ROOT / "dist" / "native" / "LeLe-Manager"
BASE_LIBRARY = Path("_internal") / "base_library.zip"


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_bundle_manifest(bundle: Path) -> dict[str, str]:
    manifest: dict[str, str] = {}

    for path in sorted(bundle.rglob("*")):
        if not path.is_file():
            continue

        relative = path.relative_to(bundle)

        if relative == BASE_LIBRARY:
            with zipfile.ZipFile(path) as archive:
                for member in sorted(archive.namelist()):
                    if member.endswith("/"):
                        continue
                    key = f"{relative}!/{member}"
                    manifest[key] = hashlib.sha256(
                        archive.read(member)
                    ).hexdigest()
            continue

        manifest[str(relative)] = sha256(path)

    return manifest


def build_snapshot(destination: Path) -> dict[str, str]:
    shutil.rmtree(ROOT / "build" / "native", ignore_errors=True)
    shutil.rmtree(ROOT / "dist" / "native", ignore_errors=True)

    run(sys.executable, str(BUILD_SCRIPT))

    if not NATIVE_BUNDLE.is_dir():
        raise SystemExit(
            f"native bundle missing after build: {NATIVE_BUNDLE}"
        )

    shutil.copytree(NATIVE_BUNDLE, destination)
    return normalized_bundle_manifest(destination)


def compare(
    first: dict[str, str],
    second: dict[str, str],
) -> list[str]:
    failures: list[str] = []

    first_paths = set(first)
    second_paths = set(second)

    for path in sorted(first_paths - second_paths):
        failures.append(f"missing from second build: {path}")

    for path in sorted(second_paths - first_paths):
        failures.append(f"missing from first build: {path}")

    for path in sorted(first_paths & second_paths):
        if first[path] != second[path]:
            failures.append(
                f"content differs: {path}: "
                f"{first[path]} != {second[path]}"
            )

    return failures


def main() -> int:
    with tempfile.TemporaryDirectory(
        prefix="lele-manager-native-repro-"
    ) as temporary:
        temp_root = Path(temporary)
        first_dir = temp_root / "first"
        second_dir = temp_root / "second"

        print("==> First clean native build")
        first = build_snapshot(first_dir)

        print("==> Second clean native build")
        second = build_snapshot(second_dir)

        failures = compare(first, second)

        if failures:
            print(
                "ERRORE: normalized native bundle reproducibility failed.",
                file=sys.stderr,
            )
            for failure in failures:
                print(f"  - {failure}", file=sys.stderr)
            return 1

        print()
        print(
            "OK: normalized native bundle payload is reproducible "
            f"across {len(first)} content entries."
        )
        print(
            "Known base_library.zip member-order differences and "
            "outer archive timestamp metadata are outside this comparison."
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
