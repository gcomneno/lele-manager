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


def test_editor_metadata_options_are_complete_deterministic_and_read_only(monkeypatch) -> None:
    df = pd.DataFrame(
        [
            {"id": "1", "topic": " Python ", "source": "note", "tags": ["pytest", "python"]},
            {"id": "2", "topic": "python", "source": "Book", "tags": ["pytest", ""]},
            {"id": "3", "topic": "git", "source": "note", "tags": ["git", "PyTest"]},
            {"id": "4", "topic": " ", "source": None, "tags": None},
            {"id": "5", "topic": float("nan"), "source": pd.NA, "tags": [pd.NA, " "]},
            {"id": "6", "topic": pd.NA, "source": pd.NaT, "tags": [pd.NaT, float("nan")]},
            {"id": "7", "topic": pd.NaT, "source": float("nan"), "tags": [" "]},
        ]
    )
    monkeypatch.setattr(server_mod, "load_lessons_df", lambda: df)

    response = TestClient(app).get("/editor/metadata-options")

    assert response.status_code == 200
    assert response.json() == {
        "topics": [{"value": "Python", "count": 2}, {"value": "git", "count": 1}],
        "tags": [{"value": "pytest", "count": 3}, {"value": "git", "count": 1}, {"value": "python", "count": 1}],
        "sources": [{"value": "note", "count": 2}, {"value": "Book", "count": 1}],
    }


def test_editor_metadata_options_empty_projection(monkeypatch) -> None:
    monkeypatch.setattr(server_mod, "load_lessons_df", lambda: pd.DataFrame())

    response = TestClient(app).get("/editor/metadata-options")

    assert response.status_code == 200
    assert response.json() == {"topics": [], "tags": [], "sources": []}


def test_ui_redirects_to_app() -> None:
    client = TestClient(app)
    resp = client.get("/ui", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"].endswith("/app/#/")
