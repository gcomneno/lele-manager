from lele_manager.application.lesson_writing import CanonicalLessonSnapshot
from lele_manager.core.assistant_context import render_assistant_context


def _lesson(
    lesson_id: str,
    *,
    title: str | None = None,
    text: str = "Canonical lesson body.",
    topic: str | None = "python",
    tags: list[str] | None = None,
    lifecycle: str = "active",
    source: str | None = None,
    superseded_by: str | None = None,
    relationships: dict[str, tuple[str, ...]] | None = None,
) -> CanonicalLessonSnapshot:
    return CanonicalLessonSnapshot(
        lesson_id=lesson_id,
        relative_path=f"{lesson_id}.md",
        canonical_revision="secret-revision-fingerprint",
        text=text,
        topic=topic,
        source=source,
        importance=3,
        tags=tags or [],
        date="2026-09-23",
        title=title,
        reviewed_at="2026-09-20",
        review_interval_days=30,
        lifecycle=lifecycle,  # type: ignore[arg-type]
        superseded_by=superseded_by,
        relationships=relationships or {},  # type: ignore[arg-type]
    )


def test_assistant_context_is_deterministic_and_human_readable() -> None:
    lessons = (
        _lesson(
            "python/alpha",
            title="Alpha",
            text="Prefer explicit contracts.",
            tags=["api", "testing"],
            relationships={
                "extends": ("python/base",),
                "see-also": ("testing/contracts",),
            },
        ),
        _lesson(
            "python/beta",
            title="Beta",
            text="Fail closed at authority boundaries.",
            lifecycle="review-needed",
        ),
    )

    first = render_assistant_context(lessons)
    second = render_assistant_context(lessons)

    assert first == second
    assert "# LeLe Assistant Context" in first
    assert "2 LeLe" in first
    assert "## Alpha" in first
    assert "ID: `python/alpha`" in first
    assert "Lifecycle: `active`" in first
    assert "Topic: `python`" in first
    assert "Tags: `api`, `testing`" in first
    assert "Prefer explicit contracts." in first
    assert "extends → `python/base`" in first
    assert "see-also → `testing/contracts`" in first
    assert "Lifecycle: `review-needed`" in first
    assert "Fail closed at authority boundaries." in first


def test_assistant_context_omits_unrelated_internal_state() -> None:
    markdown = render_assistant_context(
        (
            _lesson(
                "python/alpha",
                title="Alpha",
                source="internal-notes",
            ),
        )
    )

    assert "secret-revision-fingerprint" not in markdown
    assert "relative_path" not in markdown
    assert "canonical_revision" not in markdown
    assert "rank" not in markdown
    assert "hybrid_score" not in markdown
    assert "semantic" not in markdown
    assert "model" not in markdown
    assert "runtime" not in markdown


def test_assistant_context_represents_lifecycle_and_supersession() -> None:
    markdown = render_assistant_context(
        (
            _lesson(
                "python/old",
                title="Old guidance",
                lifecycle="deprecated",
                superseded_by="python/current",
            ),
        )
    )

    assert "Lifecycle: `deprecated`" in markdown
    assert "Superseded by: `python/current`" in markdown


def test_assistant_context_preserves_input_order() -> None:
    markdown = render_assistant_context(
        (
            _lesson("python/bravo", title="Bravo"),
            _lesson("python/alpha", title="Alpha"),
        )
    )

    assert markdown.index("## Bravo") < markdown.index("## Alpha")


def test_assistant_context_empty_scope_is_explicit() -> None:
    markdown = render_assistant_context(())

    assert "# LeLe Assistant Context" in markdown
    assert "0 LeLe" in markdown
    assert "No LeLe selected." in markdown
