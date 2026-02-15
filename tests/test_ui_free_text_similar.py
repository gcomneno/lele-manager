from pathlib import Path

def test_ui_has_free_text_similarity_search() -> None:
    html = Path("src/lele_manager/api/ui.html").read_text(encoding="utf-8")
    assert 'id="freeText"' in html
    assert 'id="btnFreeSimilar"' in html
    assert 'fetch("/similar"' in html or "fetch('/similar'" in html
