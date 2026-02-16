from fastapi.testclient import TestClient


def test_editor_suggest_matches_similar(tmp_path, monkeypatch) -> None:
    from lele_manager.api import server

    # dataset minimo
    data_path = tmp_path / "lessons.jsonl"
    data_path.write_text(
        '{"id":"1","text":"hello world","topic":"t"}\n{"id":"2","text":"hello there","topic":"t"}\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(server, "get_data_path", lambda: data_path)

    client = TestClient(server.app)

    payload = {"text": "hello", "top_k": 5, "min_score": 0.0}

    r1 = client.post("/similar", json=payload)
    assert r1.status_code in (200, 503, 400)

    r2 = client.post("/editor/suggest", json=payload)
    assert r2.status_code == r1.status_code

    if r1.status_code == 200:
        assert r2.json() == r1.json()
