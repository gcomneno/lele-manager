from pathlib import Path

import lele_manager.launcher as launcher


def test_prepare_runtime_creates_required_directories(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data = tmp_path / "data" / "lessons.jsonl"
    model = tmp_path / "cache" / "topic_model.joblib"
    vault = tmp_path / "vault"

    monkeypatch.setattr(launcher, "resolve_data_path", lambda: data)
    monkeypatch.setattr(launcher, "resolve_model_path", lambda: model)
    monkeypatch.setattr(launcher, "resolve_vault_dir", lambda: vault)

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
