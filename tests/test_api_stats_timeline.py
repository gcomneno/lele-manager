import pandas as pd
from fastapi.testclient import TestClient

from lele_manager.api import server as server_mod
from lele_manager.api.server import app


def test_stats_and_timeline_api(monkeypatch) -> None:
    df = pd.DataFrame(
        [
            {
                "id": "python/a",
                "text": "pytest layout",
                "topic": "python",
                "importance": 4,
                "tags": ["python"],
                "date": "2026-07-01",
            },
            {
                "id": "git/b",
                "text": "branching",
                "topic": "git",
                "importance": 3,
                "tags": ["git"],
                "date": "2026-07-05",
            },
        ]
    )
    monkeypatch.setattr(server_mod, "load_lessons_df", lambda: df)

    client = TestClient(app)

    stats = client.get("/stats/summary")
    assert stats.status_code == 200
    body = stats.json()
    assert body["n_lessons"] == 2
    assert body["n_topics"] == 2

    timeline = client.get("/stats/timeline", params={"group_by": "topic"})
    assert timeline.status_code == 200
    buckets = timeline.json()["buckets"]
    assert any(b["key"] == "python" for b in buckets)


def test_ui_redirects_to_app() -> None:
    client = TestClient(app)
    resp = client.get("/ui", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"].endswith("/app/#/")
