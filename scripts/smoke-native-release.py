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

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
