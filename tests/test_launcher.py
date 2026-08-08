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
