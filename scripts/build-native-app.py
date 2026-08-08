#!/usr/bin/env python3
"""Build the native LeLe Manager application bundle with PyInstaller."""

from __future__ import annotations

import shutil
import tomllib
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "LeLe-Manager"
BUILD_ROOT = ROOT / "build" / "native"
DIST_ROOT = ROOT / "dist" / "native"
PYPROJECT = ROOT / "pyproject.toml"


def project_version() -> str:
    with PYPROJECT.open("rb") as stream:
        data = tomllib.load(stream)
    return str(data["project"]["version"])


def verify_installed_version() -> None:
    expected = project_version()

    try:
        installed = version("lele-manager")
    except PackageNotFoundError as exc:
        raise SystemExit(
            "ERRORE: lele-manager non risulta installato nell'ambiente di "
            "build. Installa il checkout corrente prima della build nativa."
        ) from exc

    if installed != expected:
        raise SystemExit(
            "ERRORE: metadata lele-manager non allineata al checkout: "
            f"installata={installed}, attesa={expected}. "
            'Riallinea l\'ambiente con: python -m pip install -e ".[dev]"'
        )


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def build_gui() -> None:
    run(
        sys.executable,
        str(ROOT / "scripts" / "build-gui.py"),
    )


def clean_native_outputs() -> None:
    shutil.rmtree(BUILD_ROOT, ignore_errors=True)
    shutil.rmtree(DIST_ROOT, ignore_errors=True)


def build_native_bundle() -> None:
    launcher = ROOT / "src" / "lele_manager" / "launcher.py"

    run(
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name",
        APP_NAME,
        "--distpath",
        str(DIST_ROOT),
        "--workpath",
        str(BUILD_ROOT),
        "--specpath",
        str(BUILD_ROOT),
        "--collect-data",
        "lele_manager",
        str(launcher),
    )


def main() -> int:
    print("==> Verifying installed application version")
    verify_installed_version()

    print("==> Building compiled GUI")
    build_gui()

    print("==> Cleaning previous native bundle")
    clean_native_outputs()

    print("==> Building native application bundle")
    build_native_bundle()

    bundle = DIST_ROOT / APP_NAME

    if not bundle.is_dir():
        raise SystemExit(f"ERRORE: bundle nativo non creato: {bundle}")

    print()
    print("OK: native application bundle:")
    print(f"    {bundle}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
