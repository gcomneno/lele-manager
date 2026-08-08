#!/usr/bin/env python3
"""Create an end-user release archive from a native PyInstaller bundle."""

from __future__ import annotations

import platform
import shutil
import sys
import tarfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
DIST_NATIVE = ROOT / "dist" / "native"
RELEASE_DIR = ROOT / "dist" / "release"
APP_NAME = "LeLe-Manager"


def project_version() -> str:
    with PYPROJECT.open("rb") as stream:
        data = tomllib.load(stream)
    return str(data["project"]["version"])


def normalized_architecture() -> str:
    machine = platform.machine().lower()

    aliases = {
        "amd64": "x86_64",
        "x86_64": "x86_64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }

    return aliases.get(machine, machine)


def require_linux() -> None:
    if sys.platform != "linux":
        raise SystemExit(
            "ERRORE: questo primo packaging step supporta soltanto Linux."
        )


def main() -> int:
    require_linux()

    version = project_version()
    architecture = normalized_architecture()

    source = DIST_NATIVE / APP_NAME
    executable = source / APP_NAME
    guide = ROOT / "packaging" / "guides" / "LEGGIMI_PRIMA-Linux.txt"

    if not source.is_dir():
        raise SystemExit(
            f"ERRORE: bundle nativo assente: {source}\n"
            "Esegui prima scripts/build-native-app.sh."
        )

    if not executable.is_file():
        raise SystemExit(f"ERRORE: eseguibile assente: {executable}")

    if not guide.is_file():
        raise SystemExit(f"ERRORE: guida assente: {guide}")

    RELEASE_DIR.mkdir(parents=True, exist_ok=True)

    package_name = f"{APP_NAME}-v{version}-Linux-{architecture}"
    staging = RELEASE_DIR / package_name
    archive = RELEASE_DIR / f"{package_name}.tar.gz"

    if staging.exists():
        shutil.rmtree(staging)

    if archive.exists():
        archive.unlink()

    shutil.copytree(source, staging / APP_NAME)
    shutil.copy2(guide, staging / "LEGGIMI_PRIMA.txt")

    with tarfile.open(archive, "w:gz") as output:
        output.add(staging, arcname=package_name)

    shutil.rmtree(staging)

    print(f"Versione:     {version}")
    print(f"Piattaforma:  Linux")
    print(f"Architettura: {architecture}")
    print(f"Artefatto:    {archive}")
    print(f"Dimensione:   {archive.stat().st_size} byte")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
