#!/usr/bin/env python3
"""Build the LeLe Manager Svelte GUI and copy it into the Python package."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
FRONTEND_DIST = FRONTEND / "dist"
TARGET = ROOT / "src" / "lele_manager" / "gui" / "static"


def npm_executable() -> str:
    npm = shutil.which("npm")
    if npm is None:
        raise SystemExit("ERRORE: npm non trovato nel PATH.")
    return npm


def run(*args: str) -> None:
    subprocess.run(args, cwd=FRONTEND, check=True)


def install_dependencies(npm: str) -> None:
    if (FRONTEND / "package-lock.json").is_file():
        run(npm, "ci")
    else:
        run(npm, "install")


def build_frontend(npm: str) -> None:
    run(npm, "run", "build")


def copy_distribution() -> None:
    if not FRONTEND_DIST.is_dir():
        raise SystemExit(
            f"ERRORE: build frontend assente: {FRONTEND_DIST}"
        )

    shutil.rmtree(TARGET, ignore_errors=True)
    shutil.copytree(FRONTEND_DIST, TARGET)


def main() -> int:
    npm = npm_executable()

    print("==> Building LeLe Manager GUI (Vite + Svelte)")
    install_dependencies(npm)
    build_frontend(npm)

    print("==> Copying dist -> src/lele_manager/gui/static")
    copy_distribution()

    print(f"OK: GUI build in {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
