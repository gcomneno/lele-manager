import json
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from lele_manager.api import server
from lele_manager.ml.topic_model import save_topic_model, train_topic_model


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def test_health_without_data_and_model(tmp_path, monkeypatch) -> None:
    """Se DATA_PATH e MODEL_PATH puntano a file inesistenti, /health deve dire has_data=False, has_model=False."""
    data_path = tmp_path / "data" / "lessons.jsonl"
    model_path = tmp_path / "models" / "topic_model.joblib"

    # Garantisco che non esistano
    assert not data_path.exists()
    assert not model_path.exists()

    # Patcho i path usati dal server
    monkeypatch.setattr(server, "DATA_PATH", data_path, raising=False)
    monkeypatch.setattr(server, "MODEL_PATH", model_path, raising=False)

    client = TestClient(server.app)

    resp = client.get("/health")
    assert resp.status_code == 200

    payload = resp.json()
    assert payload.get("status") == "ok"
    assert payload.get("has_data") is False
    assert payload.get("has_model") is False


def test_health_with_data_and_model_present(tmp_path, monkeypatch) -> None:
    """Se DATA_PATH e MODEL_PATH esistono, /health deve dire has_data=True, has_model=True."""
    data_path = tmp_path / "data" / "lessons.jsonl"
    model_path = tmp_path / "models" / "topic_model.joblib"

    monkeypatch.setattr(server, "DATA_PATH", data_path, raising=False)
    monkeypatch.setattr(server, "MODEL_PATH", model_path, raising=False)

    # Creo data file
    _write_jsonl(
        data_path,
        [
            {
                "id": "1",
                "text": "LeLe di test",
                "topic": "python",
                "source": "note",
                "importance": 3,
                "tags": ["t"],
                "date": "2025-01-01",
                "title": "T",
            }
        ],
    )

    # Creo model file (qui basta che esista: /health controlla solo exists())
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_bytes(b"dummy-model-bytes")

    client = TestClient(server.app)

    resp = client.get("/health")
    assert resp.status_code == 200

    payload = resp.json()
    assert payload.get("status") == "ok"
    assert payload.get("has_data") is True
    assert payload.get("has_model") is True


def test_lessons_with_nan_and_tags(tmp_path, monkeypatch) -> None:
    """Verifica che /lessons gestisca correttamente NaN/NaT e tags non-list senza esplodere."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    data_path = data_dir / "lessons.jsonl"

    # Creo un piccolo DataFrame con:
    # - date presenti e mancanti
    # - title presente e NaN
    # - tags come lista e come stringa (che deve diventare null lato API se non list)
    df = pd.DataFrame(
        [
            {
                "id": "1",
                "text": "LeLe con tutti i campi",
                "topic": "test-topic",
                "source": "note",
                "importance": 3,
                "tags": ["a", "b"],
                "date": "2025-01-01",
                "title": "Prima LeLe",
            },
            {
                "id": "2",
                "text": "LeLe con NaN e tags strani",
                "topic": None,
                "source": None,
                "importance": None,
                "tags": "non_una_lista",
                "date": pd.NaT,
                "title": pd.NA,
            },
        ]
    )

    # Salvo come JSONL compatibile con il loader (una LeLe per riga)
    with data_path.open("w", encoding="utf-8") as f:
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            rec: dict[str, object] = {}
            for k, v in row_dict.items():
                if k == "tags":
                    # Lasciamo tags così com'è: lista o stringa.
                    # Sarà la logica dell'API a decidere se renderla lista o null.
                    rec[k] = v
                else:
                    # Per gli altri campi possiamo usare pd.isna in sicurezza.
                    if pd.isna(v):
                        rec[k] = None
                    else:
                        rec[k] = v
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Patcho il DATA_PATH del server
    monkeypatch.setattr(server, "DATA_PATH", data_path, raising=False)

    client = TestClient(server.app)

    resp = client.get("/lessons?limit=10")
    assert resp.status_code == 200

    lessons = resp.json()
    assert isinstance(lessons, list)
    assert len(lessons) == 2

    first, second = lessons

    # Prima LeLe: campi compilati
    assert first["id"] == "1"
    assert first["topic"] == "test-topic"
    assert first["source"] == "note"
    assert first["importance"] == 3
    assert first["tags"] == ["a", "b"]

    # La data può arrivare come "2025-01-01" oppure "2025-01-01 00:00:00"
    date_value = first["date"]
    assert isinstance(date_value, str)
    assert date_value.startswith("2025-01-01")

    assert first["title"] == "Prima LeLe"

    # Seconda LeLe: topic/source/date/title possono diventare null,
    # tags non-list deve essere trasformato in null (None) dall'API.
    assert second["id"] == "2"
    # importance None → JSON null
    assert second["importance"] is None
    # tags era stringa → ci aspettiamo null
    assert second["tags"] is None
    # date e title erano NaT/NA → ci aspettiamo null
    assert second["date"] is None
    assert second["title"] is None


def test_get_lesson_by_id_200_and_404(tmp_path, monkeypatch) -> None:
    """GET /lessons/{id}: 200 se esiste, 404 se non esiste."""
    data_path = tmp_path / "data" / "lessons.jsonl"
    monkeypatch.setattr(server, "DATA_PATH", data_path, raising=False)

    _write_jsonl(
        data_path,
        [
            {
                "id": "1",
                "text": "LeLe Python common",
                "topic": "python",
                "source": "note",
                "importance": 3,
                "tags": ["python"],
                "date": "2025-01-01",
                "title": "Uno",
            },
            {
                "id": "2",
                "text": "LeLe C++ common",
                "topic": "cpp",
                "source": "note",
                "importance": 2,
                "tags": ["cpp"],
                "date": "2025-01-02",
                "title": "Due",
            },
        ],
    )

    client = TestClient(server.app)

    ok = client.get("/lessons/1")
    assert ok.status_code == 200
    payload = ok.json()
    assert payload["id"] == "1"
    assert payload["topic"] == "python"
    assert payload["source"] == "note"
    assert payload["importance"] == 3
    assert payload["tags"] == ["python"]
    assert isinstance(payload["date"], str)
    assert payload["date"].startswith("2025-01-01")

    assert payload["title"] == "Uno"

    missing = client.get("/lessons/does-not-exist")
    assert missing.status_code == 404


def test_similar_returns_503_when_model_missing(tmp_path, monkeypatch) -> None:
    """GET /lessons/{id}/similar: 503 se MODEL_PATH non esiste."""
    data_path = tmp_path / "data" / "lessons.jsonl"
    model_path = tmp_path / "models" / "topic_model.joblib"

    monkeypatch.setattr(server, "DATA_PATH", data_path, raising=False)
    monkeypatch.setattr(server, "MODEL_PATH", model_path, raising=False)

    _write_jsonl(
        data_path,
        [
            {"id": "1", "text": "python common pytest", "topic": "python", "importance": 3},
            {"id": "2", "text": "cpp common cin", "topic": "cpp", "importance": 2},
            {"id": "3", "text": "python common fixtures", "topic": "python", "importance": 3},
        ],
    )

    # Garantisco che il modello NON esista
    assert not model_path.exists()

    client = TestClient(server.app)
    resp = client.get("/lessons/1/similar?top_k=5&min_score=0.0")
    assert resp.status_code == 503
    detail = resp.json().get("detail", "")
    assert "Modello" in detail or "modello" in detail


def test_similar_with_model_present_returns_results(tmp_path, monkeypatch) -> None:
    """GET /lessons/{id}/similar: 200 e results non vuoto quando modello e dati esistono."""
    data_path = tmp_path / "data" / "lessons.jsonl"
    model_path = tmp_path / "models" / "topic_model.joblib"

    monkeypatch.setattr(server, "DATA_PATH", data_path, raising=False)
    monkeypatch.setattr(server, "MODEL_PATH", model_path, raising=False)

    records = [
        {
            "id": "1",
            "text": "python common pytest fixtures",
            "topic": "python",
            "source": "note",
            "importance": 3,
        },
        {
            "id": "2",
            "text": "python common list comprehension",
            "topic": "python",
            "source": "note",
            "importance": 3,
        },
        {
            "id": "3",
            "text": "cpp common cin getline",
            "topic": "cpp",
            "source": "note",
            "importance": 2,
        },
    ]
    _write_jsonl(data_path, records)

    # Alleno e salvo un modello reale (serve per /similar: viene caricato e usato per costruire l'indice)
    df = pd.DataFrame(records)
    pipeline = train_topic_model(df)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    save_topic_model(pipeline, str(model_path))

    client = TestClient(server.app)
    resp = client.get("/lessons/1/similar?top_k=5&min_score=0.0")
    assert resp.status_code == 200

    payload = resp.json()
    assert "query" in payload
    assert "results" in payload
    assert payload["query"] == "python common pytest fixtures"

    results = payload["results"]
    assert isinstance(results, list)
    assert len(results) >= 1

    # Non deve includere self-match
    assert all(item["id"] != "1" for item in results)

    # Shape minima
    first = results[0]
    assert "id" in first and "score" in first and "text_preview" in first
    assert isinstance(first["score"], (int, float))
    assert isinstance(first["text_preview"], str)
