#!/usr/bin/env python3
"""Create an end-user release archive from a native PyInstaller bundle."""

from __future__ import annotations

import platform
import shutil
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
DIST_NATIVE = ROOT / "dist" / "native"
RELEASE_DIR = ROOT / "dist" / "release"
APP_NAME = "LeLe-Manager"
LINUX_INSTALLER = ROOT / "packaging" / "linux" / "install.sh"
LINUX_ICON = ROOT / "frontend" / "public" / "favicon.svg"


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


def platform_contract() -> tuple[str, str, str]:
    """Return release OS label, guide suffix, and archive format."""
    if sys.platform.startswith("linux"):
        return "Linux", "Linux", "tar.gz"

    if sys.platform == "darwin":
        return "macOS", "macOS", "zip"

    if sys.platform == "win32":
        return "Windows", "Windows", "zip"

    raise SystemExit(f"ERRORE: piattaforma non supportata: {sys.platform}")


def create_tar_gz(source: Path, archive: Path, package_name: str) -> None:
    with tarfile.open(archive, "w:gz") as output:
        output.add(source, arcname=package_name)


def create_zip(source: Path, archive: Path, package_name: str) -> None:
    with zipfile.ZipFile(
        archive,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as output:
        for path in source.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(source)
            output.write(path, Path(package_name) / relative)


def main() -> int:
    os_label, guide_suffix, archive_format = platform_contract()
    version = project_version()
    architecture = normalized_architecture()

    source = DIST_NATIVE / APP_NAME
    executable_name = f"{APP_NAME}.exe" if os_label == "Windows" else APP_NAME
    executable = source / executable_name
    guide = (
        ROOT
        / "packaging"
        / "guides"
        / f"LEGGIMI_PRIMA-{guide_suffix}.txt"
    )

    if not source.is_dir():
        raise SystemExit(
            f"ERRORE: bundle nativo assente: {source}\n"
            "Esegui prima scripts/build-native-app.sh."
        )

    if not executable.is_file():
        raise SystemExit(f"ERRORE: eseguibile assente: {executable}")

    if not guide.is_file():
        raise SystemExit(f"ERRORE: guida assente: {guide}")

    if os_label == "Linux":
        if not LINUX_INSTALLER.is_file():
            raise SystemExit(
                f"ERRORE: installer Linux assente: {LINUX_INSTALLER}"
            )
        if not LINUX_INSTALLER.stat().st_mode & 0o111:
            raise SystemExit(
                f"ERRORE: installer Linux non eseguibile: {LINUX_INSTALLER}"
            )
        if not LINUX_ICON.is_file():
            raise SystemExit(f"ERRORE: icona Linux assente: {LINUX_ICON}")

    RELEASE_DIR.mkdir(parents=True, exist_ok=True)

    package_name = f"{APP_NAME}-v{version}-{os_label}-{architecture}"
    staging = RELEASE_DIR / package_name

    extension = ".tar.gz" if archive_format == "tar.gz" else ".zip"
    archive = RELEASE_DIR / f"{package_name}{extension}"

    if staging.exists():
        shutil.rmtree(staging)

    if archive.exists():
        archive.unlink()

    shutil.copytree(source, staging / APP_NAME)
    shutil.copy2(guide, staging / "LEGGIMI_PRIMA.txt")
    if os_label == "Linux":
        shutil.copy2(LINUX_INSTALLER, staging / "install.sh")
        shutil.copy2(LINUX_ICON, staging / "lele-manager.svg")

    if archive_format == "tar.gz":
        create_tar_gz(staging, archive, package_name)
    else:
        create_zip(staging, archive, package_name)

    shutil.rmtree(staging)

    print(f"Versione:     {version}")
    print(f"Piattaforma:  {os_label}")
    print(f"Architettura: {architecture}")
    print(f"Formato:      {archive_format}")
    print(f"Artefatto:    {archive}")
    print(f"Dimensione:   {archive.stat().st_size} byte")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
