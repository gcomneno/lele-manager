import json
import subprocess
import sys
import joblib

from pathlib import Path
from fastapi.testclient import TestClient
from lele_manager.api import server


def run_cmd(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        check=False,
        capture_output=True,
        text=True,
    )


def write_jsonl(path: Path, records: list[dict]) -> None:
    lines = [json.dumps(rec, ensure_ascii=False) for rec in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_train_topic_model_two_topics_succeeds(tmp_path: Path) -> None:
    """Dataset con almeno 2 topic diversi: il training deve andare a buon fine."""
    data_path = tmp_path / "lessons.jsonl"
    model_path = tmp_path / "topic_model.joblib"

    records = [
        {"id": "1", "text": "LeLe Python su pytest", "topic": "python"},
        {"id": "2", "text": "LeLe C++ su std::cin", "topic": "cpp"},
        {"id": "3", "text": "Altra LeLe Python", "topic": "python"},
    ]
    write_jsonl(data_path, records)

    cmd = [
        sys.executable,
        "-m",
        "lele_manager.cli.train_topic_model",
        "--input",
        str(data_path),
        "--output",
        str(model_path),
        "--overwrite",
    ]
    result = run_cmd(cmd)

    assert (
        result.returncode == 0
    ), f"train_topic_model failed: {result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    assert model_path.exists(), "Il file del modello non è stato creato"

    pipeline = joblib.load(model_path)
    assert hasattr(pipeline, "predict")


def test_train_topic_model_single_topic_fails_human_no_traceback(tmp_path: Path) -> None:
    """Dataset con un solo topic: deve fallire senza stacktrace e con messaggio umano."""
    data_path = tmp_path / "lessons_single_topic.jsonl"
    model_path = tmp_path / "topic_model_single.joblib"

    records = [
        {"id": "1", "text": "Solo Python 1", "topic": "python"},
        {"id": "2", "text": "Solo Python 2", "topic": "python"},
    ]
    write_jsonl(data_path, records)

    cmd = [
        sys.executable,
        "-m",
        "lele_manager.cli.train_topic_model",
        "--input",
        str(data_path),
        "--output",
        str(model_path),
        "--overwrite",
    ]
    result = run_cmd(cmd)

    assert result.returncode != 0, "train_topic_model doveva fallire con un solo topic"
    assert not model_path.exists()
    assert "Traceback" not in (result.stderr or ""), f"Non vogliamo stacktrace.\nSTDERR:\n{result.stderr}"
    assert "[errore]" in (result.stderr or result.stdout)
    assert "almeno 2 topic" in (result.stderr + result.stdout)


def test_train_topic_model_missing_topic_column_fails_human_no_traceback(tmp_path: Path) -> None:
    """Dataset senza colonna topic: deve fallire senza stacktrace e con messaggio chiaro."""
    data_path = tmp_path / "lessons_missing_topic.jsonl"
    model_path = tmp_path / "topic_model_missing_topic.joblib"

    records = [
        {"id": "1", "text": "Manca topic 1"},
        {"id": "2", "text": "Manca topic 2"},
    ]
    write_jsonl(data_path, records)

    cmd = [
        sys.executable,
        "-m",
        "lele_manager.cli.train_topic_model",
        "--input",
        str(data_path),
        "--output",
        str(model_path),
        "--overwrite",
    ]
    result = run_cmd(cmd)

    assert result.returncode != 0
    assert not model_path.exists()
    assert "Traceback" not in (result.stderr or ""), f"Non vogliamo stacktrace.\nSTDERR:\n{result.stderr}"
    combined = (result.stderr or "") + (result.stdout or "")
    assert "[errore]" in combined
    assert "topic" in combined.lower()


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def test_train_topic_single_topic_returns_400_not_500(tmp_path, monkeypatch) -> None:
    # Dataset a singolo topic: deve fallire 400 (non 500) con messaggio umano
    data_path = tmp_path / "data" / "lessons.jsonl"
    model_path = tmp_path / "models" / "topic_model.joblib"

    monkeypatch.setattr(server, "DATA_PATH", data_path, raising=False)
    monkeypatch.setattr(server, "MODEL_PATH", model_path, raising=False)

    _write_jsonl(
        data_path,
        [
            {"id": "1", "text": "common python pytest fixtures", "topic": "python"},
            {"id": "2", "text": "common python list comprehension", "topic": "python"},
            {"id": "3", "text": "riga sporca", "topic": None},
        ],
    )

    client = TestClient(server.app)
    resp = client.post("/train/topic")
    assert resp.status_code == 400
    detail = (resp.json() or {}).get("detail", "")
    assert "almeno 2 topic" in detail.lower()
    assert not model_path.exists()


def test_train_topic_two_topics_succeeds(tmp_path, monkeypatch) -> None:
    # Due topic e almeno 1 token comune (min_df=2): deve andare 200
    data_path = tmp_path / "data" / "lessons.jsonl"
    model_path = tmp_path / "models" / "topic_model.joblib"

    monkeypatch.setattr(server, "DATA_PATH", data_path, raising=False)
    monkeypatch.setattr(server, "MODEL_PATH", model_path, raising=False)

    _write_jsonl(
        data_path,
        [
            {"id": "1", "text": "common pytest fixtures", "topic": "python"},
            {"id": "2", "text": "common cin getline", "topic": "cpp"},
            {"id": "3", "text": "riga sporca", "topic": None},
        ],
    )

    client = TestClient(server.app)
    resp = client.post("/train/topic")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["n_lessons"] == 2
    assert payload["topics"] == ["cpp", "python"]
    assert model_path.exists()

def test_train_topic_two_topics_disjoint_text_returns_400_human_message(tmp_path, monkeypatch) -> None:
    # Due topic ma testi completamente disgiunti: con min_df=2 TF-IDF può restare senza termini.
    # L'API deve rispondere 400 con messaggio umano (non 500).
    data_path = tmp_path / "data" / "lessons.jsonl"
    model_path = tmp_path / "models" / "topic_model.joblib"

    monkeypatch.setattr(server, "DATA_PATH", data_path, raising=False)
    monkeypatch.setattr(server, "MODEL_PATH", model_path, raising=False)

    _write_jsonl(
        data_path,
        [
            {"id": "1", "text": "pytest fixtures", "topic": "python"},
            {"id": "2", "text": "cin getline", "topic": "cpp"},
            {"id": "3", "text": "riga sporca", "topic": None},
        ],
    )

    client = TestClient(server.app)
    resp = client.post("/train/topic")
    assert resp.status_code == 400

    detail = (resp.json() or {}).get("detail", "")
    low = detail.lower()
    # Deve essere "umano": accettiamo che contenga uno di questi segnali.
    assert ("tf-idf" in low) or ("termini" in low) or ("vettorizz" in low) or ("vocabulary" in low)

    assert not model_path.exists()
