from datetime import date

import pytest

from lele_manager.core.freshness import (
    DEFAULT_REVIEW_INTERVAL_DAYS,
    FreshnessValidationError,
    assess_freshness,
    normalize_review_interval_days,
    normalize_reviewed_at,
)


def test_active_recent_lesson_is_not_review_needed() -> None:
    result = assess_freshness(
        lifecycle="active",
        lesson_date="2026-01-01",
        as_of=date(2026, 6, 1),
    )

    assert result.review_needed is False
    assert result.age_days == 151
    assert result.review_interval_days == DEFAULT_REVIEW_INTERVAL_DAYS
    assert result.reasons == ()


def test_age_signal_becomes_due_at_review_interval_boundary() -> None:
    result = assess_freshness(
        lesson_date="2025-08-20",
        as_of=date(2026, 8, 20),
    )

    assert result.review_needed is True
    assert result.age_days == 365
    assert [reason.code for reason in result.reasons] == ["review-overdue"]


def test_reviewed_at_accepts_yaml_date_object() -> None:
    assert normalize_reviewed_at(date(2026, 8, 1)) == "2026-08-01"


def test_explicit_review_date_replaces_creation_date_as_age_baseline() -> None:
    result = assess_freshness(
        lesson_date="2020-01-01",
        reviewed_at="2026-08-01",
        as_of=date(2026, 8, 20),
    )

    assert result.review_needed is False
    assert result.baseline_date == "2026-08-01"
    assert result.age_days == 19


def test_per_lesson_review_interval_is_explicit_and_bounded() -> None:
    result = assess_freshness(
        lesson_date="2026-07-01",
        review_interval_days=30,
        as_of=date(2026, 8, 20),
    )

    assert result.review_needed is True
    assert result.review_interval_days == 30
    assert result.age_days == 50


@pytest.mark.parametrize("lifecycle", ["deprecated", "archived"])
def test_terminal_lifecycle_states_do_not_create_review_noise(lifecycle: str) -> None:
    result = assess_freshness(
        lifecycle=lifecycle,
        lesson_date="2020-01-01",
        incoming_relationships={
            "corrects": ["python/newer"],
            "extends": ["python/extension"],
        },
        superseded_by="python/replacement",
        as_of=date(2026, 8, 20),
    )

    assert result.review_needed is False
    assert result.age_days is None
    assert result.reasons == ()


def test_explicit_review_needed_lifecycle_is_an_explainable_signal() -> None:
    result = assess_freshness(
        lifecycle="review-needed",
        lesson_date="2026-08-19",
        as_of=date(2026, 8, 20),
    )

    assert result.review_needed is True
    assert [reason.code for reason in result.reasons] == [
        "lifecycle-review-needed"
    ]


def test_only_maintained_relation_types_contribute_relation_signals() -> None:
    result = assess_freshness(
        lesson_date="2026-08-19",
        incoming_relationships={
            "corrects": ["python/correction-b", "python/correction-a"],
            "extends": ["python/extension"],
            "contradicts": ["python/contradiction"],
            "see-also": ["python/related"],
            "derives-from": ["python/derived"],
        },
        related_lesson_dates={
            "python/correction-a": "2026-08-20",
            "python/correction-b": "2026-08-20",
            "python/extension": "2026-08-20",
            "python/contradiction": "2026-08-20",
            "python/related": "2026-08-20",
            "python/derived": "2026-08-20",
        },
        as_of=date(2026, 8, 20),
    )

    assert [reason.code for reason in result.reasons] == [
        "corrected-by-related-knowledge",
        "extended-by-related-knowledge",
    ]
    assert result.reasons[0].related_lesson_ids == (
        "python/correction-a",
        "python/correction-b",
    )
    assert result.reasons[1].related_lesson_ids == ("python/extension",)


def test_same_date_and_older_related_knowledge_do_not_trigger_review() -> None:
    result = assess_freshness(
        lesson_date="2026-08-19",
        incoming_relationships={
            "corrects": ["python/same-day"],
            "extends": ["python/older"],
        },
        related_lesson_dates={
            "python/same-day": "2026-08-19",
            "python/older": "2026-08-18",
        },
        as_of=date(2026, 8, 20),
    )

    assert result.review_needed is False
    assert result.reasons == ()


def test_review_after_related_knowledge_clears_relation_signal() -> None:
    result = assess_freshness(
        lesson_date="2026-08-01",
        reviewed_at="2026-08-20",
        incoming_relationships={
            "corrects": ["python/correction"],
            "extends": ["python/extension"],
        },
        related_lesson_dates={
            "python/correction": "2026-08-19",
            "python/extension": "2026-08-18",
        },
        as_of=date(2026, 8, 20),
    )

    assert result.review_needed is False
    assert result.baseline_date == "2026-08-20"
    assert result.reasons == ()


def test_unknown_related_lesson_date_does_not_invent_newer_signal() -> None:
    result = assess_freshness(
        lesson_date="2026-08-19",
        incoming_relationships={
            "corrects": ["python/no-date"],
            "extends": ["python/free-form-date"],
        },
        related_lesson_dates={
            "python/no-date": None,
            "python/free-form-date": "newer sometime",
        },
        as_of=date(2026, 8, 20),
    )

    assert result.review_needed is False
    assert result.reasons == ()


def test_superseded_by_is_an_explicit_relation_based_signal() -> None:
    result = assess_freshness(
        lesson_date="2026-08-19",
        superseded_by="python/replacement",
        as_of=date(2026, 8, 20),
    )

    assert result.review_needed is True
    assert [reason.code for reason in result.reasons] == ["superseded"]
    assert result.reasons[0].related_lesson_ids == ("python/replacement",)


def test_reason_order_is_deterministic_and_explainable() -> None:
    result = assess_freshness(
        lifecycle="review-needed",
        lesson_date="2020-01-01",
        incoming_relationships={
            "extends": ["python/extension"],
            "corrects": ["python/correction"],
        },
        related_lesson_dates={
            "python/extension": "2026-08-20",
            "python/correction": "2026-08-20",
        },
        superseded_by="python/replacement",
        as_of=date(2026, 8, 20),
    )

    assert [reason.code for reason in result.reasons] == [
        "lifecycle-review-needed",
        "review-overdue",
        "corrected-by-related-knowledge",
        "extended-by-related-knowledge",
        "superseded",
    ]


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("", "YYYY-MM-DD"),
        ("20-08-2026", "YYYY-MM-DD"),
        ("2026-02-30", "valid calendar date"),
        (123, "ISO date string"),
    ],
)
def test_reviewed_at_rejects_malformed_canonical_values(
    value: object,
    message: str,
) -> None:
    with pytest.raises(FreshnessValidationError, match=message):
        normalize_reviewed_at(value)


@pytest.mark.parametrize("value", [0, -1, 3651, True, "365"])
def test_review_interval_rejects_invalid_or_unbounded_values(value: object) -> None:
    with pytest.raises(FreshnessValidationError):
        normalize_review_interval_days(value)


def test_unparseable_legacy_lesson_date_does_not_invent_age() -> None:
    result = assess_freshness(
        lesson_date="legacy free-form date",
        as_of=date(2026, 8, 20),
    )

    assert result.review_needed is False
    assert result.baseline_date is None
    assert result.age_days is None
