import json
from pathlib import Path

from fastapi.testclient import TestClient

from lele_manager.api import server


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _setup_data_and_train(client: TestClient, data_path: Path, records: list[dict]) -> None:
    _write_jsonl(data_path, records)
    resp = client.post("/train/topic")
    assert resp.status_code == 200, resp.text


def test_similar_min_score_too_high_returns_empty_results(tmp_path, monkeypatch) -> None:
    data_path = tmp_path / "data" / "lessons.jsonl"
    model_path = tmp_path / "models" / "topic_model.joblib"

    monkeypatch.setattr(server, "DATA_PATH", data_path, raising=False)
    monkeypatch.setattr(server, "MODEL_PATH", model_path, raising=False)

    client = TestClient(server.app)

    # Training OK: 2 topic + token comune ("common") per min_df=2
    _setup_data_and_train(
        client,
        data_path,
        [
            {"id": "1", "text": "common pytest fixtures conftest", "topic": "python"},
            {"id": "2", "text": "common cin getline istream", "topic": "cpp"},
            {"id": "3", "text": "riga sporca", "topic": None},
        ],
    )

    # min_score alto: dopo il filtro self-match deve risultare vuoto
    resp = client.get("/lessons/1/similar", params={"top_k": 20, "min_score": 0.999})
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["query"]
    assert payload["results"] == []


def test_similar_top_k_bigger_than_dataset_does_not_explode(tmp_path, monkeypatch) -> None:
    data_path = tmp_path / "data" / "lessons.jsonl"
    model_path = tmp_path / "models" / "topic_model.joblib"

    monkeypatch.setattr(server, "DATA_PATH", data_path, raising=False)
    monkeypatch.setattr(server, "MODEL_PATH", model_path, raising=False)

    client = TestClient(server.app)

    _setup_data_and_train(
        client,
        data_path,
        [
            {"id": "1", "text": "common pytest fixtures conftest", "topic": "python"},
            {"id": "2", "text": "common pytest parametrize fixtures", "topic": "python"},
            {"id": "3", "text": "common cin getline istream", "topic": "cpp"},
            {"id": "4", "text": "common cout endl ostream", "topic": "cpp"},
        ],
    )

    resp = client.get("/lessons/1/similar", params={"top_k": 20, "min_score": 0.0})
    assert resp.status_code == 200, resp.text
    payload = resp.json()

    results = payload["results"]
    # 4 lezioni totali, 1 è la query → al massimo 3 risultati
    assert len(results) <= 3
    assert len(results) <= 20
    assert all(item["id"] != "1" for item in results)
    # Niente duplicati
    ids = [item["id"] for item in results]
    assert len(ids) == len(set(ids))


def test_similar_with_empty_text_lesson_does_not_500(tmp_path, monkeypatch) -> None:
    data_path = tmp_path / "data" / "lessons.jsonl"
    model_path = tmp_path / "models" / "topic_model.joblib"

    monkeypatch.setattr(server, "DATA_PATH", data_path, raising=False)
    monkeypatch.setattr(server, "MODEL_PATH", model_path, raising=False)

    client = TestClient(server.app)

    _setup_data_and_train(
        client,
        data_path,
        [
            {"id": "1", "text": "common pytest fixtures conftest", "topic": "python"},
            {"id": "2", "text": "common cin getline istream", "topic": "cpp"},
            # Lesson con text vuoto: resta nel dataset, ma non deve far esplodere la similarità
            {"id": "3", "text": "", "topic": None},
        ],
    )

    resp = client.get("/lessons/1/similar", params={"top_k": 20, "min_score": 0.01})
    assert resp.status_code == 200, resp.text
    payload = resp.json()

    # Non vogliamo self-match, e idealmente la riga vuota non dovrebbe entrare sopra soglia
    ids = [item["id"] for item in payload["results"]]
    assert "1" not in ids
    assert "3" not in ids
