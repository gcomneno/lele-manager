import json

import pandas as pd
from fastapi.testclient import TestClient

from lele_manager.api import server


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
    # Non vincolo topic/source, ma non devono far esplodere il JSON.
    # importance None → JSON null
    assert second["importance"] is None
    # tags era stringa → ci aspettiamo null
    assert second["tags"] is None
    # date e title erano NaT/NA → ci aspettiamo null
    assert second["date"] is None
    assert second["title"] is None
