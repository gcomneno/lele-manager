from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lele_manager.api.server import app


GUI_INDEX = Path("src/lele_manager/gui/static/index.html")


pytestmark = pytest.mark.skipif(
    not GUI_INDEX.is_file(),
    reason="GUI not built (run ./scripts/build-gui.sh)",
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_root_redirects_to_app(client: TestClient) -> None:
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (307, 308)
    assert resp.headers["location"].endswith("/app/")


def test_gui_app_index(client: TestClient) -> None:
    resp = client.get("/app/")
    assert resp.status_code == 200
    assert "LeLe Manager" in resp.text
    assert 'id="app"' in resp.text


def test_gui_assets_served(client: TestClient) -> None:
    index = GUI_INDEX.read_text(encoding="utf-8")
    # Vite injects hashed asset paths; ensure at least one /app/assets reference exists.
    assert "/app/assets/" in index

    asset_path = index.split('/app/assets/')[1].split('"')[0]
    resp = client.get(f"/app/assets/{asset_path}")
    assert resp.status_code == 200
