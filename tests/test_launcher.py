import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

import lele_manager.launcher as launcher
from lele_manager.core.vault_registry import ActiveVaultContext


@contextmanager
def local_http_service(
    *,
    status: int = 200,
    content_type: str = "application/json",
    body: bytes = b'{"product_name": "LeLe Manager"}',
):
    """Run a real loopback HTTP service representing a port occupant."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/about":
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            self.send_response(404)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer((launcher.DEFAULT_HOST, 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        yield int(server.server_address[1])
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_prepare_runtime_creates_required_directories(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data = tmp_path / "data" / "vaults" / "id" / "lessons.jsonl"
    model = tmp_path / "cache" / "vaults" / "id" / "topic_model.joblib"
    vault = tmp_path / "vault"

    monkeypatch.setattr(launcher, "active_vault_context", lambda: ActiveVaultContext("id", "Test", vault, data, data.parent / "candidates.json", model, "id"))

    assert launcher.prepare_runtime() == (data, model, vault)

    assert data.parent.is_dir()
    assert model.parent.is_dir()
    assert vault.is_dir()


def test_open_browser_when_health_is_ready(monkeypatch) -> None:
    opened: list[str] = []

    monkeypatch.setattr(
        launcher,
        "wait_until_ready",
        lambda url, timeout: True,
    )
    monkeypatch.setattr(
        launcher.webbrowser,
        "open",
        lambda url: opened.append(url),
    )

    launcher.open_browser_when_ready(
        "http://127.0.0.1:8765/health",
        "http://127.0.0.1:8765/app/",
    )

    assert opened == ["http://127.0.0.1:8765/app/"]


def test_browser_stays_closed_when_health_never_becomes_ready(
    monkeypatch,
) -> None:
    opened: list[str] = []

    monkeypatch.setattr(
        launcher,
        "wait_until_ready",
        lambda url, timeout: False,
    )
    monkeypatch.setattr(
        launcher.webbrowser,
        "open",
        lambda url: opened.append(url),
    )

    launcher.open_browser_when_ready(
        "http://127.0.0.1:8765/health",
        "http://127.0.0.1:8765/app/",
    )

    assert opened == []


def test_find_available_port_falls_back_when_preferred_port_is_busy() -> None:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind((launcher.DEFAULT_HOST, 0))
        occupied.listen()
        busy_port = int(occupied.getsockname()[1])

        selected = launcher.find_available_port(
            launcher.DEFAULT_HOST,
            busy_port,
        )

    assert selected != busy_port
    assert selected > 0


def test_find_available_port_prefers_a_free_preferred_port() -> None:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
        candidate.bind((launcher.DEFAULT_HOST, 0))
        preferred_port = int(candidate.getsockname()[1])

    assert (
        launcher.find_available_port(launcher.DEFAULT_HOST, preferred_port)
        == preferred_port
    )


def test_instance_probe_recognizes_lele_manager_without_version_matching() -> None:
    body = json.dumps(
        {"product_name": "LeLe Manager", "version": "0.9.0"}
    ).encode()

    with local_http_service(body=body) as port:
        assert launcher.is_running_lele_manager(port) is True


@pytest.mark.parametrize(
    ("status", "content_type", "body"),
    [
        (200, "text/html", b'{"product_name": "LeLe Manager"}'),
        (200, "application/json", b"not-json"),
        (200, "application/json", b'{"product_name": "Other app"}'),
        (503, "application/json", b'{"product_name": "LeLe Manager"}'),
    ],
)
def test_instance_probe_rejects_unexpected_port_occupants(
    status: int,
    content_type: str,
    body: bytes,
) -> None:
    with local_http_service(
        status=status,
        content_type=content_type,
        body=body,
    ) as port:
        assert launcher.is_running_lele_manager(port) is False


def test_instance_probe_handles_unavailable_port() -> None:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((launcher.DEFAULT_HOST, 0))
        unavailable_port = int(sock.getsockname()[1])

    assert launcher.is_running_lele_manager(unavailable_port) is False


def test_release_automation_hooks_are_disabled_by_default() -> None:
    environment: dict[str, str] = {}

    assert launcher.resolve_automation_port(environment) is None
    assert launcher.browser_opening_enabled(environment) is True


def test_release_automation_hooks_accept_explicit_smoke_values() -> None:
    environment = {
        launcher.AUTOMATION_PORT_ENV: "43210",
        launcher.AUTOMATION_NO_BROWSER_ENV: "1",
    }

    assert launcher.resolve_automation_port(environment) == 43210
    assert launcher.browser_opening_enabled(environment) is False


def test_automation_port_keeps_fixed_port_semantics(monkeypatch) -> None:
    monkeypatch.setattr(
        launcher,
        "is_running_lele_manager",
        lambda port: (_ for _ in ()).throw(AssertionError("unexpected probe")),
    )

    assert launcher.resolve_launch_target(43210) == (43210, False)


def test_release_automation_port_rejects_invalid_values() -> None:
    for raw in ("not-a-port", "0", "65536", "-1"):
        environment = {launcher.AUTOMATION_PORT_ENV: raw}

        try:
            launcher.resolve_automation_port(environment)
        except ValueError as exc:
            assert launcher.AUTOMATION_PORT_ENV in str(exc)
        else:
            raise AssertionError(f"invalid automation port accepted: {raw}")


def test_main_treats_keyboard_interrupt_as_clean_shutdown(monkeypatch) -> None:
    class InterruptingServer:
        def __init__(self, config) -> None:
            self.config = config

        def run(self) -> None:
            raise KeyboardInterrupt

    monkeypatch.setattr(
        launcher,
        "prepare_runtime",
        lambda: (Path("/tmp/data"), Path("/tmp/model"), Path("/tmp/vault")),
    )
    monkeypatch.setattr(launcher, "resolve_automation_port", lambda: None)
    monkeypatch.setattr(launcher, "is_running_lele_manager", lambda port: False)
    monkeypatch.setattr(launcher, "find_available_port", lambda: 43210)
    monkeypatch.setattr(launcher, "browser_opening_enabled", lambda: False)
    monkeypatch.setattr(launcher.uvicorn, "Server", InterruptingServer)

    try:
        result = launcher.main()
    except KeyboardInterrupt:
        raise AssertionError(
            "launcher.main() propagated KeyboardInterrupt instead of "
            "treating Ctrl+C as a clean shutdown"
        ) from None

    assert result == 0


def test_main_reuses_running_lele_manager_at_preferred_origin(monkeypatch) -> None:
    opened: list[str] = []

    class UnexpectedServer:
        def __init__(self, config) -> None:
            raise AssertionError("a reusable LeLe Manager must not be restarted")

    with local_http_service() as preferred_port:
        monkeypatch.setattr(launcher, "DEFAULT_PORT", preferred_port)
        monkeypatch.setattr(
            launcher,
            "prepare_runtime",
            lambda: (Path("/tmp/data"), Path("/tmp/model"), Path("/tmp/vault")),
        )
        monkeypatch.setattr(launcher, "resolve_automation_port", lambda: None)
        monkeypatch.setattr(launcher.webbrowser, "open", opened.append)
        monkeypatch.setattr(launcher.uvicorn, "Server", UnexpectedServer)

        assert launcher.main() == 0

    assert opened == [f"http://{launcher.DEFAULT_HOST}:{preferred_port}/app/"]


def test_main_reuse_respects_browser_disabled_automation(monkeypatch) -> None:
    class UnexpectedServer:
        def __init__(self, config) -> None:
            raise AssertionError("a reusable LeLe Manager must not be restarted")

    with local_http_service() as preferred_port:
        monkeypatch.setattr(launcher, "DEFAULT_PORT", preferred_port)
        monkeypatch.setattr(
            launcher,
            "prepare_runtime",
            lambda: (Path("/tmp/data"), Path("/tmp/model"), Path("/tmp/vault")),
        )
        monkeypatch.setattr(launcher, "resolve_automation_port", lambda: None)
        monkeypatch.setattr(launcher, "browser_opening_enabled", lambda: False)
        monkeypatch.setattr(
            launcher.webbrowser,
            "open",
            lambda url: (_ for _ in ()).throw(AssertionError("browser opened")),
        )
        monkeypatch.setattr(launcher.uvicorn, "Server", UnexpectedServer)

        assert launcher.main() == 0


def test_main_does_not_attach_to_an_unrelated_preferred_port(monkeypatch) -> None:
    captured_ports: list[int] = []

    class InterruptingServer:
        def __init__(self, config) -> None:
            captured_ports.append(config.port)

        def run(self) -> None:
            raise KeyboardInterrupt

    unrelated_body = json.dumps(
        {"product_name": "Another local app", "status": "ok"}
    ).encode()
    with local_http_service(body=unrelated_body) as preferred_port:
        fallback_port = preferred_port + 1
        monkeypatch.setattr(launcher, "DEFAULT_PORT", preferred_port)
        monkeypatch.setattr(
            launcher,
            "prepare_runtime",
            lambda: (Path("/tmp/data"), Path("/tmp/model"), Path("/tmp/vault")),
        )
        monkeypatch.setattr(launcher, "resolve_automation_port", lambda: None)
        monkeypatch.setattr(
            launcher,
            "find_available_port",
            lambda: fallback_port,
        )
        monkeypatch.setattr(launcher, "browser_opening_enabled", lambda: False)
        monkeypatch.setattr(launcher.uvicorn, "Server", InterruptingServer)

        assert launcher.main() == 0
        assert launcher.is_running_lele_manager(preferred_port) is False

    assert captured_ports == [fallback_port]
