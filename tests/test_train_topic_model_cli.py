import json
import subprocess
import sys
from pathlib import Path

import joblib


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
