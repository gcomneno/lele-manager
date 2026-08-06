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
    assert "/app/favicon.svg" in resp.text


def test_gui_assets_served(client: TestClient) -> None:
    index = GUI_INDEX.read_text(encoding="utf-8")
    # Vite injects hashed asset paths; ensure at least one /app/assets reference exists.
    assert "/app/assets/" in index

    asset_path = index.split("/app/assets/")[1].split('"')[0]
    resp = client.get(f"/app/assets/{asset_path}")
    assert resp.status_code == 200


def test_packaged_brand_assets_are_served(client: TestClient) -> None:
    for asset in (
        "brand/lele-manager-mark.svg",
        "brand/lele-manager-lockup.svg",
        "brand/giadaware-monkey.svg",
        "favicon.svg",
    ):
        resp = client.get(f"/app/{asset}")
        assert resp.status_code == 200, asset
        assert resp.headers["content-type"].startswith("image/svg+xml"), asset
        assert "<svg" in resp.text, asset


def test_served_lockup_contains_literal_product_name(client: TestClient) -> None:
    resp = client.get("/app/brand/lele-manager-lockup.svg")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert "LeLe Manager" in resp.text


def test_unknown_gui_route_falls_back_to_index(
    client: TestClient,
) -> None:
    resp = client.get("/app/lessons/example")

    assert resp.status_code == 200
    assert "LeLe Manager" in resp.text
    assert 'id="app"' in resp.text


def test_gui_route_rejects_path_traversal() -> None:
    route = next(
        route
        for route in app.routes
        if getattr(route, "path", None) == "/app/{full_path:path}"
    )

    response = route.endpoint("../../../../pyproject.toml")

    assert Path(response.path).resolve() == GUI_INDEX.resolve()
