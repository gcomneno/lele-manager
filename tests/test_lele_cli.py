import types
from typing import Any, Dict, List

from lele_manager.cli import lele as lele_cli


class FakeResponse:
    def __init__(self, status_code: int = 200, json_data: Any = None, text: str = "") -> None:
        self.status_code = status_code
        self._json = json_data if json_data is not None else []
        self.text = text

    def json(self) -> Any:  # pragma: no cover - semplice accessor
        return self._json


class FakeClient:
    """Finto httpx.Client che registra le chiamate senza fare rete."""

    def __init__(self, base_url: str, timeout: float, calls: List[Any]) -> None:  # noqa: D401
        self.base_url = base_url
        self.timeout = timeout
        self._calls = calls

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: D401
        return False

    def post(self, path: str, json: Dict[str, Any] | None = None) -> FakeResponse:
        self._calls.append(("POST", path, json))
        return FakeResponse(status_code=200, json_data=[])

    def get(self, path: str, params: Dict[str, Any] | None = None) -> FakeResponse:
        # Usiamo una risposta dummy per eventuali future estensioni
        self._calls.append(("GET", path, params))
        dummy = {
            "id": "dummy",
            "text": "dummy text",
            "topic": None,
            "source": None,
            "importance": None,
            "tags": None,
            "date": None,
            "title": None,
        }
        return FakeResponse(status_code=200, json_data=dummy)


def test_lele_search_builds_correct_payload(monkeypatch, capsys) -> None:
    """Verifica che `lele search` costruisca il payload giusto per /lessons/search."""
    calls: List[Any] = []

    def fake_client_ctor(base_url: str, timeout: float) -> FakeClient:
        return FakeClient(base_url, timeout, calls)

    fake_httpx = types.SimpleNamespace(Client=fake_client_ctor)
    monkeypatch.setattr(lele_cli, "httpx", fake_httpx, raising=False)

    argv = [
        "--base-url",
        "http://api",
        "search",
        "pytest",
        "--topic",
        "python",
        "--source",
        "note",
        "--min-importance",
        "3",
        "--max-importance",
        "5",
        "--limit",
        "7",
        "--json",
    ]
    # Non deve sollevare, e deve terminare con exit code 0
    try:
        lele_cli.main(argv)
    except SystemExit as e:  # main chiama sys.exit(...)
        assert e.code == 0

    out, err = capsys.readouterr()
    # Non ci interessa il contenuto, ma il comando deve aver fatto almeno una chiamata POST
    assert err == ""

    assert len(calls) == 1
    method, path, payload = calls[0]
    assert method == "POST"
    assert path == "/lessons/search"
    assert payload == {
        "q": "pytest",
        "topic_in": ["python"],
        "source_in": ["note"],
        "importance_gte": 3,
        "importance_lte": 5,
        "limit": 7,
    }
