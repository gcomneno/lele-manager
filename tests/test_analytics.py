import pandas as pd

from lele_manager.core.analytics import compute_stats_summary, compute_timeline


def test_compute_stats_summary() -> None:
    df = pd.DataFrame(
        [
            {
                "id": "a",
                "text": "hello world",
                "topic": "python",
                "importance": 4,
                "tags": ["python", "pytest"],
            },
            {
                "id": "b",
                "text": "git flow",
                "topic": "git",
                "importance": 2,
                "tags": ["git", "python"],
            },
        ]
    )
    stats = compute_stats_summary(df)
    assert stats["n_lessons"] == 2
    assert stats["n_topics"] == 2
    assert stats["n_unique_tags"] == 3
    assert stats["avg_text_length"] > 0
    assert stats["avg_importance"] == 3.0


def test_compute_timeline_by_month() -> None:
    df = pd.DataFrame(
        [
            {"id": "a", "date": "2026-01-15", "topic": "python"},
            {"id": "b", "date": "2026-01-20", "topic": "git"},
            {"id": "c", "date": "2026-02-01", "topic": "python"},
        ]
    )
    tl = compute_timeline(df, group_by="month")
    assert tl["group_by"] == "month"
    keys = [b["key"] for b in tl["buckets"]]
    assert "2026-01" in keys
    assert "2026-02" in keys


def test_compute_timeline_by_topic() -> None:
    df = pd.DataFrame(
        [
            {"id": "a", "topic": "python"},
            {"id": "b", "topic": "python"},
            {"id": "c", "topic": "git"},
        ]
    )
    tl = compute_timeline(df, group_by="topic")
    python = next(b for b in tl["buckets"] if b["key"] == "python")
    assert python["count"] == 2
