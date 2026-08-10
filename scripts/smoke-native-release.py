#!/usr/bin/env python3
"""Smoke-test the actual published-style native LeLe Manager release archive."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import tomllib
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
RELEASE_DIR = ROOT / "dist" / "release"
APP_NAME = "LeLe-Manager"

NO_BROWSER_ENV = "LELE_MANAGER_NO_BROWSER"
PORT_ENV = "LELE_MANAGER_PORT"

HTTP_TIMEOUT_SECONDS = 2.0
STARTUP_TIMEOUT_SECONDS = 30.0
PROCESS_STOP_TIMEOUT_SECONDS = 10.0

EXPECTED_RUNTIME_PATH_KEYS = {
    "vault",
    "application_data",
    "lesson_projection",
    "candidate_staging",
    "cache",
    "topic_model",
}


def project_version() -> str:
    with PYPROJECT.open("rb") as stream:
        data = tomllib.load(stream)
    return str(data["project"]["version"])


def platform_contract() -> tuple[str, str]:
    if sys.platform.startswith("linux"):
        return "Linux", ".tar.gz"
    if sys.platform == "darwin":
        return "macOS", ".zip"
    if sys.platform == "win32":
        return "Windows", ".zip"
    raise RuntimeError(f"Piattaforma non supportata: {sys.platform}")


def find_release_archive(
    release_dir: Path,
    version: str,
    os_label: str,
    extension: str,
) -> Path:
    pattern = f"{APP_NAME}-v{version}-{os_label}-*{extension}"
    matches = sorted(
        path
        for path in release_dir.glob(pattern)
        if path.is_file()
    )

    if len(matches) != 1:
        raise RuntimeError(
            "Atteso esattamente un archive native-release "
            f"per {os_label} {version}, trovati {len(matches)}: "
            f"{matches}"
        )

    return matches[0]


def _safe_zip_destination(root: Path, member: str) -> Path:
    destination = (root / member).resolve()
    resolved_root = root.resolve()

    if not destination.is_relative_to(resolved_root):
        raise RuntimeError(
            f"Archive ZIP non sicuro, percorso fuori destinazione: {member}"
        )

    return destination


def extract_release_archive(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)

    if archive.name.endswith(".tar.gz"):
        with tarfile.open(archive, "r:gz") as stream:
            stream.extractall(destination, filter="data")
        return

    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as stream:
            for member in stream.infolist():
                extracted = _safe_zip_destination(
                    destination,
                    member.filename,
                )
                stream.extract(member, destination)

                unix_mode = (member.external_attr >> 16) & 0o777
                if unix_mode and extracted.is_file():
                    extracted.chmod(unix_mode)
        return

    raise RuntimeError(f"Formato archive non supportato: {archive}")


def find_packaged_executable(
    extraction_root: Path,
    version: str,
    os_label: str,
) -> Path:
    executable_name = (
        f"{APP_NAME}.exe"
        if os_label == "Windows"
        else APP_NAME
    )
    candidates = sorted(
        extraction_root.glob(
            f"{APP_NAME}-v{version}-{os_label}-*/"
            f"{APP_NAME}/{executable_name}"
        )
    )

    if len(candidates) != 1 or not candidates[0].is_file():
        raise RuntimeError(
            "Eseguibile packaged non trovato in modo univoco: "
            f"{candidates}"
        )

    return candidates[0]


def find_linux_installer(extraction_root: Path, version: str) -> Path:
    candidates = sorted(
        extraction_root.glob(
            f"{APP_NAME}-v{version}-Linux-*/install.sh"
        )
    )

    if len(candidates) != 1 or not candidates[0].is_file():
        raise RuntimeError(
            "Installer Linux packaged non trovato in modo univoco: "
            f"{candidates}"
        )

    if not candidates[0].stat().st_mode & 0o111:
        raise RuntimeError(
            f"Installer Linux packaged non eseguibile: {candidates[0]}"
        )

    return candidates[0]


def find_linux_icon(extraction_root: Path, version: str) -> Path:
    candidates = sorted(
        extraction_root.glob(
            f"{APP_NAME}-v{version}-Linux-*/lele-manager.svg"
        )
    )
    if len(candidates) != 1 or not candidates[0].is_file():
        raise RuntimeError(
            "Icona Linux packaged non trovata in modo univoco: "
            f"{candidates}"
        )
    return candidates[0]


def choose_free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _fetch_bytes(url: str) -> bytes:
    with urllib.request.urlopen(  # nosec B310
        url,
        timeout=HTTP_TIMEOUT_SECONDS,
    ) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(
                f"HTTP {response.status} durante il road test: {url}"
            )
        return response.read()


def fetch_text(url: str) -> str:
    return _fetch_bytes(url).decode("utf-8")


def fetch_json(url: str) -> dict[str, Any]:
    payload = json.loads(fetch_text(url))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Payload JSON non-object da {url}")
    return payload


def wait_until_ready(
    process: subprocess.Popen[str],
    base_url: str,
) -> dict[str, Any]:
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    health_url = f"{base_url}/health"

    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                "L'eseguibile packaged è terminato prima di diventare pronto "
                f"(exit code {process.returncode})."
            )

        try:
            payload = fetch_json(health_url)
            if payload.get("status") == "ok":
                return payload
        except (
            urllib.error.URLError,
            TimeoutError,
            OSError,
            json.JSONDecodeError,
            RuntimeError,
        ):
            pass

        time.sleep(0.1)

    raise RuntimeError(
        "Timeout in attesa di /health dall'eseguibile packaged."
    )


def terminate_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return

    process.terminate()
    try:
        process.wait(timeout=PROCESS_STOP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=PROCESS_STOP_TIMEOUT_SECONDS)


def assert_isolated_runtime_paths(
    settings: dict[str, Any],
    extraction_root: Path,
    runtime_root: Path,
) -> None:
    items = settings.get("paths")
    if not isinstance(items, list):
        raise RuntimeError("/settings/runtime non contiene una lista paths.")

    seen: set[str] = set()
    resolved_release = extraction_root.resolve()
    resolved_runtime = runtime_root.resolve()

    for item in items:
        if not isinstance(item, dict):
            raise RuntimeError("Elemento runtime path non valido.")

        key = item.get("key")
        raw_path = item.get("path")

        if not isinstance(key, str) or not isinstance(raw_path, str):
            raise RuntimeError("Runtime path privo di key/path valida.")

        seen.add(key)
        effective = Path(raw_path).resolve()

        if effective.is_relative_to(resolved_release):
            raise RuntimeError(
                f"Runtime path {key} ricade dentro il release archive: "
                f"{effective}"
            )

        if not effective.is_relative_to(resolved_runtime):
            raise RuntimeError(
                f"Runtime path {key} non è isolato nel runtime temporaneo: "
                f"{effective}"
            )

    missing = EXPECTED_RUNTIME_PATH_KEYS - seen
    if missing:
        raise RuntimeError(
            "Runtime path mancanti da /settings/runtime: "
            + ", ".join(sorted(missing))
        )


def validate_running_release(
    base_url: str,
    version: str,
    extraction_root: Path,
    runtime_root: Path,
    process: subprocess.Popen[str],
) -> None:
    health = wait_until_ready(process, base_url)
    if health.get("status") != "ok":
        raise RuntimeError("/health non riporta status=ok.")

    runtime = fetch_json(f"{base_url}/runtime/info")
    if runtime.get("version") != version:
        raise RuntimeError(
            "Versione runtime diversa dal progetto: "
            f"{runtime.get('version')!r} != {version!r}"
        )

    gui_html = fetch_text(f"{base_url}/app/")
    if "LeLe Manager" not in gui_html:
        raise RuntimeError("/app/ non identifica LeLe Manager.")

    license_text = fetch_text(f"{base_url}/app/LICENSE")
    if "MIT License" not in license_text:
        raise RuntimeError("/app/LICENSE non contiene la licenza MIT attesa.")

    about = fetch_json(f"{base_url}/about")
    if about.get("product_name") != "LeLe Manager":
        raise RuntimeError("/about espone un product_name inatteso.")
    if about.get("version") != version:
        raise RuntimeError("/about non è allineato alla versione runtime.")
    if about.get("license_id") != "MIT":
        raise RuntimeError("/about non espone license_id=MIT.")

    settings = fetch_json(f"{base_url}/settings/runtime")
    if settings.get("version") != version:
        raise RuntimeError(
            "/settings/runtime non è allineato alla versione runtime."
        )

    assert_isolated_runtime_paths(
        settings,
        extraction_root,
        runtime_root,
    )


def run_linux_installed_smoke(
    installer: Path,
    packaged_icon: Path,
    version: str,
    temporary_root: Path,
    environment: dict[str, str],
) -> None:
    install_home = temporary_root / "installed-home"
    install_data_home = temporary_root / "installed-xdg-data"
    install_bin_dir = temporary_root / "installed-bin"
    installed_runtime = temporary_root / "installed-runtime"
    install_log = temporary_root / "installed-native.log"

    installer_environment = environment.copy()
    installer_environment["HOME"] = str(install_home)
    installer_environment["XDG_DATA_HOME"] = str(install_data_home)
    installer_environment["LELE_MANAGER_INSTALL_BIN_DIR"] = str(install_bin_dir)
    installer_environment["LELE_DATA_DIR"] = str(installed_runtime / "data")
    installer_environment["LELE_CACHE_DIR"] = str(installed_runtime / "cache")
    installer_environment["LELE_VAULT_DIR"] = str(installed_runtime / "vault")

    installation = subprocess.run(
        [str(installer)],
        cwd=installer.parent,
        env=installer_environment,
        text=True,
        capture_output=True,
        check=False,
    )
    if installation.returncode != 0:
        raise RuntimeError(
            "Installer Linux packaged terminato con errore:\n"
            f"stdout:\n{installation.stdout}\n"
            f"stderr:\n{installation.stderr}"
        )

    launcher = install_bin_dir / "lele-manager"
    installed_executable = (
        install_data_home / "lele-manager" / "install" / "app" / APP_NAME
    )
    if not launcher.is_symlink() or launcher.readlink() != installed_executable:
        raise RuntimeError(
            "Il launcher Linux installato non punta al bundle stabile atteso: "
            f"{launcher}"
        )
    if not installed_executable.is_file():
        raise RuntimeError(
            "Bundle Linux installato assente: "
            f"{installed_executable}"
        )
    desktop_entry = install_data_home / "applications" / "lele-manager.desktop"
    installed_icon = (
        install_data_home / "icons/hicolor/scalable/apps/lele-manager.svg"
    )
    if not desktop_entry.is_file():
        raise RuntimeError(f"Voce desktop Linux installata assente: {desktop_entry}")
    if not installed_icon.is_file() or installed_icon.read_bytes() != packaged_icon.read_bytes():
        raise RuntimeError("Icona Linux installata assente o diversa da quella packaged.")
    desktop = desktop_entry.read_text(encoding="utf-8")
    for entry in (
        "[Desktop Entry]",
        "Type=Application",
        "Name=LeLe Manager",
        "Terminal=false",
        "Icon=lele-manager",
        "Categories=Development;",
        "StartupNotify=true",
        f'Exec="{launcher}"',
        f'TryExec="{launcher}"',
    ):
        if entry not in desktop:
            raise RuntimeError(f"Voce desktop Linux non valida, manca: {entry}")

    port = choose_free_loopback_port()
    base_url = f"http://127.0.0.1:{port}"
    installer_environment[PORT_ENV] = str(port)

    with install_log.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [str(launcher)],
            cwd=installed_executable.parent,
            env=installer_environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )

        try:
            validate_running_release(
                base_url,
                version,
                installed_executable.parent,
                installed_runtime,
                process,
            )
        finally:
            terminate_process(process)

    print("OK: installer Linux, launcher stabile e integrazione desktop verificati.")


def main() -> int:
    version = project_version()
    os_label, extension = platform_contract()
    archive = find_release_archive(
        RELEASE_DIR,
        version,
        os_label,
        extension,
    )

    print(f"Archive:     {archive}")
    print(f"Versione:    {version}")
    print(f"Piattaforma: {os_label}")

    with tempfile.TemporaryDirectory(
        prefix="lele-manager-native-road-test-"
    ) as temporary:
        temp_root = Path(temporary)
        extraction_root = temp_root / "published"
        runtime_root = temp_root / "runtime"
        log_path = temp_root / "native.log"

        extract_release_archive(archive, extraction_root)
        executable = find_packaged_executable(
            extraction_root,
            version,
            os_label,
        )
        if os_label == "Linux":
            installer = find_linux_installer(extraction_root, version)
            packaged_icon = find_linux_icon(extraction_root, version)
            print(f"Installer:    {installer}")

        port = choose_free_loopback_port()
        base_url = f"http://127.0.0.1:{port}"

        environment = os.environ.copy()
        environment.pop("LELE_DATA_PATH", None)
        environment.pop("LELE_MODEL_PATH", None)
        environment[NO_BROWSER_ENV] = "1"
        environment[PORT_ENV] = str(port)
        environment["LELE_DATA_DIR"] = str(runtime_root / "data")
        environment["LELE_CACHE_DIR"] = str(runtime_root / "cache")
        environment["LELE_VAULT_DIR"] = str(runtime_root / "vault")

        print(f"Eseguibile:  {executable}")
        print(f"Loopback:    {base_url}")

        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                [str(executable)],
                cwd=executable.parent,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
            )

            try:
                validate_running_release(
                    base_url,
                    version,
                    extraction_root,
                    runtime_root,
                    process,
                )
            finally:
                terminate_process(process)

        print("OK: published-style native archive avviato e verificato.")
        print("OK: runtime data esterni alla directory del release package.")

        if os_label == "Linux":
            run_linux_installed_smoke(
                installer,
                packaged_icon,
                version,
                temp_root,
                environment,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
