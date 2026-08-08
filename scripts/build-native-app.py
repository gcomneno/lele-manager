#!/usr/bin/env python3
"""Build the native LeLe Manager application bundle with PyInstaller."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "LeLe-Manager"
BUILD_ROOT = ROOT / "build" / "native"
DIST_ROOT = ROOT / "dist" / "native"


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def build_gui() -> None:
    run(str(ROOT / "scripts" / "build-gui.sh"))


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
