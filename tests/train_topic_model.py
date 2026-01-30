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
    # Controllo minimale: che abbia un metodo predict
    assert hasattr(pipeline, "predict")


def test_train_topic_model_single_topic_fails(tmp_path: Path) -> None:
    """Dataset con un solo topic: il training deve fallire in modo esplicito."""
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

    # Qui CI ASPETTIAMO un errore (per via del controllo "almeno 2 classi")
    assert result.returncode != 0, "train_topic_model doveva fallire con un solo topic"

    # Il modello non dovrebbe esistere (o comunque non lo usiamo)
    assert not model_path.exists()
