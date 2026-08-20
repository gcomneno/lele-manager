"""Explainable, advisory freshness signals for canonical lessons.

Freshness is derived state. It may recommend human review, but it never changes
canonical Markdown or lifecycle state by itself.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
import re
from typing import Literal

from lele_manager.core.lifecycle import LifecycleState, normalize_lifecycle


DEFAULT_REVIEW_INTERVAL_DAYS = 365
MIN_REVIEW_INTERVAL_DAYS = 1
MAX_REVIEW_INTERVAL_DAYS = 3650

FreshnessReasonCode = Literal[
    "lifecycle-review-needed",
    "review-overdue",
    "corrected-by-related-knowledge",
    "extended-by-related-knowledge",
    "superseded",
]


class FreshnessValidationError(ValueError):
    """Maintained review metadata is malformed or outside supported bounds."""


@dataclass(frozen=True)
class FreshnessReason:
    code: FreshnessReasonCode
    message: str
    related_lesson_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class FreshnessAssessment:
    """Derived, side-effect-free review prioritization for one lesson."""

    review_needed: bool
    lifecycle: LifecycleState
    baseline_date: str | None
    age_days: int | None
    review_interval_days: int
    reasons: tuple[FreshnessReason, ...]


def normalize_reviewed_at(value: object) -> str | None:
    """Normalize optional canonical ``reviewed_at`` as YYYY-MM-DD."""

    if value is None:
        return None
    if type(value) is date:
        return value.isoformat()
    if not isinstance(value, str):
        raise FreshnessValidationError("reviewed_at must be an ISO date string")

    normalized = value.strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized):
        raise FreshnessValidationError("reviewed_at must use YYYY-MM-DD")

    try:
        parsed = date.fromisoformat(normalized)
    except ValueError as exc:
        raise FreshnessValidationError("reviewed_at must be a valid calendar date") from exc

    return parsed.isoformat()


def normalize_review_interval_days(value: object) -> int | None:
    """Normalize optional canonical per-lesson review interval."""

    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise FreshnessValidationError("review_interval_days must be an integer")
    if not MIN_REVIEW_INTERVAL_DAYS <= value <= MAX_REVIEW_INTERVAL_DAYS:
        raise FreshnessValidationError(
            "review_interval_days must be between "
            f"{MIN_REVIEW_INTERVAL_DAYS} and {MAX_REVIEW_INTERVAL_DAYS}"
        )
    return value


def _lesson_date(value: object) -> date | None:
    """Best-effort legacy lesson date parsing.

    ``date`` predates the freshness contract and is intentionally free-form in
    existing data. An unparseable legacy value therefore removes the age signal
    instead of turning an otherwise readable lesson into invalid canonical
    state.
    """

    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized):
        return None
    try:
        return date.fromisoformat(normalized)
    except ValueError:
        return None


def _related_ids(
    relationships: Mapping[str, Sequence[str]] | None,
    relation_type: str,
) -> tuple[str, ...]:
    if relationships is None:
        return ()

    raw = relationships.get(relation_type)
    if raw is None or isinstance(raw, (str, bytes)):
        return ()

    values = {
        value.strip()
        for value in raw
        if isinstance(value, str) and value.strip()
    }
    return tuple(sorted(values))


def _newer_related_ids(
    relationships: Mapping[str, Sequence[str]] | None,
    relation_type: str,
    *,
    baseline: date | None,
    related_lesson_dates: Mapping[str, object] | None,
) -> tuple[str, ...]:
    """Return related lesson ids proven newer than the target baseline."""

    if baseline is None or related_lesson_dates is None:
        return ()

    newer: list[str] = []
    for lesson_id in _related_ids(relationships, relation_type):
        source_date = _lesson_date(related_lesson_dates.get(lesson_id))
        if source_date is not None and source_date > baseline:
            newer.append(lesson_id)
    return tuple(newer)


def assess_freshness(
    *,
    lifecycle: object = None,
    reviewed_at: object = None,
    review_interval_days: object = None,
    lesson_date: object = None,
    incoming_relationships: Mapping[str, Sequence[str]] | None = None,
    related_lesson_dates: Mapping[str, object] | None = None,
    superseded_by: str | None = None,
    as_of: date,
) -> FreshnessAssessment:
    """Return an explainable advisory freshness assessment.

    No canonical state is mutated or inferred. ``contradicts`` is deliberately
    excluded because contradiction review is owned by issue #215.
    """

    normalized_lifecycle = normalize_lifecycle(lifecycle)
    normalized_reviewed_at = normalize_reviewed_at(reviewed_at)
    explicit_interval = normalize_review_interval_days(review_interval_days)
    interval = explicit_interval or DEFAULT_REVIEW_INTERVAL_DAYS

    if normalized_lifecycle in {"deprecated", "archived"}:
        return FreshnessAssessment(
            review_needed=False,
            lifecycle=normalized_lifecycle,
            baseline_date=normalized_reviewed_at,
            age_days=None,
            review_interval_days=interval,
            reasons=(),
        )

    reviewed_date = (
        date.fromisoformat(normalized_reviewed_at)
        if normalized_reviewed_at is not None
        else None
    )
    baseline = reviewed_date or _lesson_date(lesson_date)
    age_days = max((as_of - baseline).days, 0) if baseline is not None else None

    reasons: list[FreshnessReason] = []

    if normalized_lifecycle == "review-needed":
        reasons.append(
            FreshnessReason(
                code="lifecycle-review-needed",
                message="The canonical lifecycle explicitly marks this lesson for review.",
            )
        )

    if age_days is not None and age_days >= interval:
        reasons.append(
            FreshnessReason(
                code="review-overdue",
                message=(
                    f"This lesson has not been reviewed for {age_days} days; "
                    f"its review interval is {interval} days."
                ),
            )
        )

    correcting_ids = _newer_related_ids(
        incoming_relationships,
        "corrects",
        baseline=baseline,
        related_lesson_dates=related_lesson_dates,
    )
    if correcting_ids:
        reasons.append(
            FreshnessReason(
                code="corrected-by-related-knowledge",
                message="Newer explicit related knowledge corrects this lesson.",
                related_lesson_ids=correcting_ids,
            )
        )

    extending_ids = _newer_related_ids(
        incoming_relationships,
        "extends",
        baseline=baseline,
        related_lesson_dates=related_lesson_dates,
    )
    if extending_ids:
        reasons.append(
            FreshnessReason(
                code="extended-by-related-knowledge",
                message="Newer explicit related knowledge extends this lesson.",
                related_lesson_ids=extending_ids,
            )
        )

    replacement = superseded_by.strip() if isinstance(superseded_by, str) else ""
    if replacement:
        reasons.append(
            FreshnessReason(
                code="superseded",
                message="This lesson names a canonical replacement.",
                related_lesson_ids=(replacement,),
            )
        )

    return FreshnessAssessment(
        review_needed=bool(reasons),
        lifecycle=normalized_lifecycle,
        baseline_date=baseline.isoformat() if baseline is not None else None,
        age_days=age_days,
        review_interval_days=interval,
        reasons=tuple(reasons),
    )
