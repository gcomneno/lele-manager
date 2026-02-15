from pathlib import Path


def test_server_imports_similarity_index_from_non_legacy_module() -> None:
    server_py = Path("src/lele_manager/api/server.py")
    text = server_py.read_text(encoding="utf-8")

    assert "from lele_manager.ml.similarity import LessonSimilarityIndex" in text
    assert "lele_manager.ml.text_ml" not in text
