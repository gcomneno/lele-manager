#!/usr/bin/env python3
"""Build the native LeLe Manager application bundle with PyInstaller."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tomllib
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
            "Riallinea l'ambiente usando requirements/native-release.txt."
        )


def validate_source_date_epoch(value: str, source: str) -> str:
    if not value or value.strip() != value or not value.isdecimal():
        raise SystemExit(
            f"ERRORE: {source} non valido: deve essere un timestamp Unix "
            "intero non negativo."
        )
    return value


def git_commit_source_date_epoch() -> str:
    try:
        completed = subprocess.run(
            (
                "git",
                "log",
                "-1",
                "--format=%ct",
                "HEAD",
            ),
            cwd=ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise SystemExit(
            "ERRORE: SOURCE_DATE_EPOCH non impostato e timestamp commit Git "
            "non disponibile. Imposta SOURCE_DATE_EPOCH a un timestamp Unix "
            "intero prima della build nativa."
        ) from exc

    return validate_source_date_epoch(
        completed.stdout.strip(),
        "timestamp commit Git",
    )


def deterministic_source_date_epoch() -> str:
    configured = os.environ.get("SOURCE_DATE_EPOCH")
    if configured is not None:
        return validate_source_date_epoch(
            configured,
            "SOURCE_DATE_EPOCH",
        )
    return git_commit_source_date_epoch()


def pyinstaller_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["SOURCE_DATE_EPOCH"] = (
        deterministic_source_date_epoch()
    )
    environment["PYTHONHASHSEED"] = "0"
    return environment


def run(
    *args: str,
    env: dict[str, str] | None = None,
) -> None:
    subprocess.run(
        args,
        cwd=ROOT,
        check=True,
        env=env,
    )


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
        env=pyinstaller_environment(),
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
