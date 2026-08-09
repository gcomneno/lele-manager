"""Desktop-style launcher for the packaged LeLe Manager web application."""

from __future__ import annotations

import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

import uvicorn

from lele_manager.api.server import app
from lele_manager.core.config import resolve_data_path, resolve_model_path
from lele_manager.core.vault import resolve_vault_dir

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
HEALTH_TIMEOUT_SECONDS = 30.0
INSTANCE_PROBE_TIMEOUT_SECONDS = 0.5
INSTANCE_PROBE_MAX_BODY_BYTES = 16 * 1024
AUTOMATION_NO_BROWSER_ENV = "LELE_MANAGER_NO_BROWSER"
AUTOMATION_PORT_ENV = "LELE_MANAGER_PORT"
PRODUCT_NAME = "LeLe Manager"


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects while probing an untrusted local port occupant."""

    def redirect_request(
        self,
        *args: object,
        **kwargs: object,
    ) -> None:
        return None


def resolve_automation_port(
    environment: dict[str, str] | None = None,
) -> int | None:
    """Resolve the optional internal fixed port used by release automation."""
    values = os.environ if environment is None else environment
    raw = values.get(AUTOMATION_PORT_ENV)

    if raw is None:
        return None

    try:
        port = int(raw)
    except ValueError as exc:
        raise ValueError(
            f"{AUTOMATION_PORT_ENV} must be an integer between 1 and 65535."
        ) from exc

    if not 1 <= port <= 65535:
        raise ValueError(
            f"{AUTOMATION_PORT_ENV} must be an integer between 1 and 65535."
        )

    return port


def browser_opening_enabled(
    environment: dict[str, str] | None = None,
) -> bool:
    """Return False only for the explicit internal release-smoke override."""
    values = os.environ if environment is None else environment
    return values.get(AUTOMATION_NO_BROWSER_ENV) != "1"


def find_available_port(
    host: str = DEFAULT_HOST,
    preferred_port: int = DEFAULT_PORT,
) -> int:
    """Use the preferred local port when free, otherwise ask the OS for one."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, preferred_port))
        except OSError:
            sock.bind((host, 0))
        return int(sock.getsockname()[1])


def is_running_lele_manager(
    port: int,
    *,
    timeout: float = INSTANCE_PROBE_TIMEOUT_SECONDS,
) -> bool:
    """Return whether a loopback port exposes LeLe Manager's product identity."""
    about_url = f"http://{DEFAULT_HOST}:{port}/about"
    request = urllib.request.Request(
        about_url,
        headers={"Accept": "application/json"},
    )
    opener = urllib.request.build_opener(_NoRedirectHandler())

    try:
        # The URL is constructed from the fixed loopback host and supplied port.
        with opener.open(request, timeout=timeout) as response:  # nosec B310
            if not 200 <= response.status < 300:
                return False
            if response.headers.get_content_type() != "application/json":
                return False

            payload_bytes = response.read(INSTANCE_PROBE_MAX_BODY_BYTES + 1)
            if len(payload_bytes) > INSTANCE_PROBE_MAX_BODY_BYTES:
                return False

        payload = json.loads(payload_bytes.decode("utf-8"))
    except (
        urllib.error.URLError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return False

    return (
        isinstance(payload, dict)
        and payload.get("product_name") == PRODUCT_NAME
    )


def resolve_launch_target(
    automation_port: int | None,
) -> tuple[int, bool]:
    """Choose the server port and whether an existing server can be reused.

    The release-smoke port override deliberately retains its fixed-port
    semantics. Normal launches reuse only a healthy local process that
    explicitly identifies itself through LeLe Manager's ``/about`` contract.
    """
    if automation_port is not None:
        return automation_port, False

    if is_running_lele_manager(DEFAULT_PORT):
        return DEFAULT_PORT, True

    return find_available_port(), False


def prepare_runtime() -> tuple[Path, Path, Path]:
    """Create the persistent runtime locations required on first launch."""
    data_path = resolve_data_path()
    model_path = resolve_model_path()
    vault_dir = resolve_vault_dir()

    data_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    vault_dir.mkdir(parents=True, exist_ok=True)

    return data_path, model_path, vault_dir


def wait_until_ready(
    url: str,
    *,
    timeout: float = HEALTH_TIMEOUT_SECONDS,
    interval: float = 0.1,
) -> bool:
    """Wait until the local health endpoint answers successfully."""
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        try:
            # Callers pass the launcher-owned http://127.0.0.1 health URL only.
            with urllib.request.urlopen(url, timeout=1.0) as response:  # nosec B310
                if 200 <= response.status < 300:
                    return True
        except (urllib.error.URLError, OSError):
            pass

        time.sleep(interval)

    return False


def open_browser_when_ready(
    health_url: str,
    app_url: str,
    *,
    timeout: float = HEALTH_TIMEOUT_SECONDS,
) -> None:
    """Open the GUI only after the local application is ready."""
    if wait_until_ready(health_url, timeout=timeout):
        webbrowser.open(app_url)


def main() -> int:
    """Prepare persistent state, start LeLe Manager, and open its GUI."""
    prepare_runtime()

    try:
        automation_port = resolve_automation_port()
    except ValueError as exc:
        raise SystemExit(f"ERRORE: {exc}") from exc

    port, reuses_existing_instance = resolve_launch_target(automation_port)
    base_url = f"http://{DEFAULT_HOST}:{port}"
    health_url = f"{base_url}/health"
    app_url = f"{base_url}/app/"

    if reuses_existing_instance:
        if browser_opening_enabled():
            webbrowser.open(app_url)
        return 0

    if browser_opening_enabled():
        browser_thread = threading.Thread(
            target=open_browser_when_ready,
            args=(health_url, app_url),
            daemon=True,
        )
        browser_thread.start()

    config = uvicorn.Config(
        app,
        host=DEFAULT_HOST,
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)

    try:
        server.run()
    except KeyboardInterrupt:
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
