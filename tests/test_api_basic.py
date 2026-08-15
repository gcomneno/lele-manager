import pytest
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


def test_runtime_info_exposes_authoritative_application_version() -> None:
    client = TestClient(server.app)

    resp = client.get("/runtime/info")

    assert resp.status_code == 200
    assert resp.json() == {"version": server.__version__}


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
    assert payload["canonical_revision"] is None

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
            {
                "id": "1",
                "text": "python common pytest",
                "topic": "python",
                "importance": 3,
            },
            {"id": "2", "text": "cpp common cin", "topic": "cpp", "importance": 2},
            {
                "id": "3",
                "text": "python common fixtures",
                "topic": "python",
                "importance": 3,
            },
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


def test_dashboard_summary_is_bounded_and_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault = tmp_path / "missing-vault"
    data = tmp_path / "lessons.jsonl"
    model = tmp_path / "topic-model.joblib"
    candidates = tmp_path / "candidates.json"

    monkeypatch.setenv("LELE_VAULT_DIR", str(vault))
    monkeypatch.setenv("LELE_DATA_PATH", str(data))
    monkeypatch.setenv("LELE_MODEL_PATH", str(model))
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(server, "DATA_PATH", data)
    monkeypatch.setattr(server, "MODEL_PATH", model)

    before = {
        "vault": vault.exists(),
        "data": data.exists(),
        "model": model.exists(),
        "candidates": candidates.exists(),
    }

    response = TestClient(server.app).get("/dashboard/summary")

    assert response.status_code == 200
    assert response.json() == {
        "health_status": "ok",
        "vault_exists": False,
        "vault_markdown_files": None,
        "projection_exists": False,
        "model_exists": False,
        "stats": None,
        "candidates": {
            "total": 0,
            "staged": 0,
            "in_review": 0,
            "rejected": 0,
            "approved": 0,
        },
    }
    assert before == {
        "vault": vault.exists(),
        "data": data.exists(),
        "model": model.exists(),
        "candidates": candidates.exists(),
    }


def test_settings_runtime_is_bounded_side_effect_free_and_version_aligned(
    tmp_path,
    monkeypatch,
) -> None:
    data = tmp_path / "data"
    cache = tmp_path / "cache"
    vault = tmp_path / "vault"

    monkeypatch.setenv("LELE_DATA_DIR", str(data))
    monkeypatch.setenv("LELE_CACHE_DIR", str(cache))
    monkeypatch.setenv("LELE_VAULT_DIR", str(vault))
    monkeypatch.delenv("LELE_DATA_PATH", raising=False)
    monkeypatch.delenv("LELE_MODEL_PATH", raising=False)
    monkeypatch.setattr(server, "DATA_PATH", None, raising=False)
    monkeypatch.setattr(server, "MODEL_PATH", None, raising=False)

    client = TestClient(server.app)
    response = client.get("/settings/runtime")
    assert response.status_code == 200

    payload = response.json()
    assert payload["version"] == client.get("/runtime/info").json()["version"]
    assert payload["health"] == {
        "status": "ok",
        "has_data": False,
        "has_model": False,
    }

    by_key = {item["key"]: item for item in payload["paths"]}
    assert set(by_key) == {
        "vault",
        "application_data",
        "vault_registry",
        "lesson_projection",
        "candidate_staging",
        "duplicate_decisions",
        "cache",
        "topic_model",
    }
    assert by_key["vault_registry"]["path"] == str(data / "vault-registry.json")

    assert by_key["vault"]["role"] == "authoritative_user_data"
    assert by_key["application_data"]["role"] == "persistent_application_state"
    assert by_key["candidate_staging"]["role"] == "persistent_application_state"
    assert by_key["duplicate_decisions"]["role"] == "persistent_application_state"
    assert by_key["lesson_projection"]["role"] == "derived_rebuildable_artifact"
    assert by_key["topic_model"]["role"] == "derived_rebuildable_artifact"
    assert by_key["cache"]["role"] == "cache_temporary_state"

    assert by_key["application_data"]["provenance"] == {
        "kind": "configuration_override",
        "variable": "LELE_DATA_DIR",
        "deprecated": False,
    }

    assert not data.exists()
    assert not cache.exists()
    assert not vault.exists()


def test_settings_runtime_identifies_legacy_file_overrides(
    tmp_path,
    monkeypatch,
) -> None:
    projection = tmp_path / "legacy" / "lessons.jsonl"
    model = tmp_path / "legacy-model" / "topic_model.joblib"

    monkeypatch.setenv("LELE_DATA_PATH", str(projection))
    monkeypatch.setenv("LELE_MODEL_PATH", str(model))
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LELE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(server, "DATA_PATH", None, raising=False)
    monkeypatch.setattr(server, "MODEL_PATH", None, raising=False)

    client = TestClient(server.app)
    payload = client.get("/settings/runtime").json()
    by_key = {item["key"]: item for item in payload["paths"]}

    assert by_key["lesson_projection"]["path"] == str(projection.resolve())
    assert by_key["lesson_projection"]["provenance"] == {
        "kind": "legacy_override",
        "variable": "LELE_DATA_PATH",
        "deprecated": True,
    }

    assert by_key["topic_model"]["path"] == str(model.resolve())
    assert by_key["topic_model"]["provenance"] == {
        "kind": "legacy_override",
        "variable": "LELE_MODEL_PATH",
        "deprecated": True,
    }

    assert not projection.parent.exists()
    assert not model.parent.exists()


def test_settings_runtime_server_overrides_do_not_claim_environment_provenance(
    tmp_path,
    monkeypatch,
) -> None:
    projection = tmp_path / "runtime" / "lessons.jsonl"
    model = tmp_path / "runtime" / "topic_model.joblib"

    monkeypatch.setenv("LELE_DATA_PATH", str(tmp_path / "env-data.jsonl"))
    monkeypatch.setenv("LELE_MODEL_PATH", str(tmp_path / "env-model.joblib"))
    monkeypatch.setattr(server, "DATA_PATH", projection, raising=False)
    monkeypatch.setattr(server, "MODEL_PATH", model, raising=False)

    client = TestClient(server.app)
    payload = client.get("/settings/runtime").json()
    by_key = {item["key"]: item for item in payload["paths"]}

    assert by_key["lesson_projection"]["path"] == str(projection)
    assert by_key["lesson_projection"]["provenance"] == {
        "kind": "runtime_override",
        "variable": None,
        "deprecated": False,
    }

    assert by_key["topic_model"]["path"] == str(model)
    assert by_key["topic_model"]["provenance"] == {
        "kind": "runtime_override",
        "variable": None,
        "deprecated": False,
    }


def test_about_is_bounded_and_uses_authoritative_version() -> None:
    client = TestClient(server.app)

    about = client.get("/about")
    assert about.status_code == 200
    payload = about.json()

    assert payload["product_name"] == "LeLe Manager"
    assert payload["version"] == client.get("/runtime/info").json()["version"]
    assert payload["license_id"] == "MIT"
    assert payload["license_url"] == "/app/LICENSE"
    assert payload["changelog_url"].endswith("/CHANGELOG.md")
    assert payload["documentation_url"].endswith("/docs/gui-user-guide.md")
    assert payload["attribution"] == "GiadaWare"
    assert "no account" in payload["local_first_statement"]
    assert "telemetry" in payload["local_first_statement"]
    assert "cloud storage" in payload["local_first_statement"]


def test_diagnostics_preview_is_exact_bounded_payload_and_side_effect_free(
    tmp_path,
    monkeypatch,
) -> None:
    data = tmp_path / "data"
    cache = tmp_path / "cache"
    vault = tmp_path / "vault"
    secret = "DO-NOT-EXPOSE-THIS-VALUE"

    monkeypatch.setenv("LELE_DATA_DIR", str(data))
    monkeypatch.setenv("LELE_CACHE_DIR", str(cache))
    monkeypatch.setenv("LELE_VAULT_DIR", str(vault))
    monkeypatch.setenv("UNRELATED_SECRET_TOKEN", secret)
    monkeypatch.setattr(server, "DATA_PATH", None, raising=False)
    monkeypatch.setattr(server, "MODEL_PATH", None, raising=False)

    client = TestClient(server.app)
    response = client.get("/diagnostics/preview")
    assert response.status_code == 200

    payload = response.json()
    assert set(payload) == {
        "product_name",
        "version",
        "python_version",
        "platform_system",
        "platform_release",
        "health",
        "paths",
    }
    assert payload["version"] == client.get("/runtime/info").json()["version"]
    assert secret not in response.text
    assert "UNRELATED_SECRET_TOKEN" not in response.text

    assert not data.exists()
    assert not cache.exists()
    assert not vault.exists()

def test_get_lesson_exposes_forward_and_derived_reverse_supersession(
    tmp_path, monkeypatch
) -> None:
    data_path = tmp_path / "data" / "lessons.jsonl"
    monkeypatch.setattr(server, "DATA_PATH", data_path, raising=False)

    _write_jsonl(
        data_path,
        [
            {
                "id": "old/a",
                "text": "Old A",
                "lifecycle": "deprecated",
                "superseded_by": "current",
            },
            {
                "id": "old/b",
                "text": "Old B",
                "lifecycle": "archived",
                "superseded_by": "current",
            },
            {
                "id": "current",
                "text": "Current knowledge",
                "lifecycle": "active",
            },
        ],
    )

    client = TestClient(server.app)

    current = client.get("/lessons/current")
    assert current.status_code == 200
    current_payload = current.json()
    assert current_payload["superseded_by"] is None
    assert current_payload["supersedes"] == ["old/a", "old/b"]
    assert current_payload["canonical_revision"] is None

    old = client.get("/lessons/old/a")
    assert old.status_code == 200
    old_payload = old.json()
    assert old_payload["lifecycle"] == "deprecated"
    assert old_payload["superseded_by"] == "current"
    assert old_payload["supersedes"] == []
