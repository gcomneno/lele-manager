from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from lele_manager.core.factual_verification import (
    EvidenceItem,
    VerificationAssessment,
    VerificationClaim,
    VerificationValidationError,
    assessment_is_stale,
)


UTC = timezone.utc


def claim(
    classification: str = "stable-factual",
) -> VerificationClaim:
    return VerificationClaim(
        claim_id="claim-1",
        text="Python 3.12 was released in October 2023.",
        classification=classification,
    )


def evidence() -> EvidenceItem:
    return EvidenceItem(
        source_id="python-3.12-release",
        source_uri="https://www.python.org/downloads/release/python-3120/",
        source_title="Python 3.12.0",
        retrieved_at=datetime(2026, 9, 25, 5, 0, tzinfo=UTC),
        excerpt="Python 3.12.0 was released on October 2, 2023.",
    )


def assessment(
    *,
    outcome: str = "supported",
    classification: str = "stable-factual",
    evidence_items: tuple[EvidenceItem, ...] | None = None,
    checked_at: datetime | None = None,
) -> VerificationAssessment:
    if evidence_items is None:
        evidence_items = (evidence(),)

    return VerificationAssessment(
        lesson_id="python/releases",
        canonical_revision="sha256:canonical-a",
        claim=claim(classification),
        outcome=outcome,
        evidence=evidence_items,
        checked_at=checked_at
        or datetime(2026, 9, 25, 6, 0, tzinfo=UTC),
        explanation="The primary release page supports the claim.",
    )


@pytest.mark.parametrize(
    "outcome",
    [
        "supported",
        "contradicted",
        "outdated",
    ],
)
def test_evidence_backed_factual_outcomes_require_evidence(
    outcome: str,
) -> None:
    with pytest.raises(
        VerificationValidationError,
        match="requires evidence",
    ):
        assessment(
            outcome=outcome,
            evidence_items=(),
        )


def test_supported_assessment_retains_bounded_primary_evidence() -> None:
    result = assessment()

    assert result.outcome == "supported"
    assert result.lesson_id == "python/releases"
    assert result.canonical_revision == "sha256:canonical-a"
    assert result.claim.classification == "stable-factual"
    assert result.evidence == (evidence(),)
    assert result.checked_at == datetime(
        2026,
        9,
        25,
        6,
        0,
        tzinfo=UTC,
    )


def test_contradicted_assessment_is_evidence_backed_not_binary_oracle() -> None:
    result = assessment(
        outcome="contradicted",
    )

    assert result.outcome == "contradicted"
    assert result.evidence
    assert result.explanation


def test_insufficient_evidence_is_valid_without_sources() -> None:
    result = assessment(
        outcome="insufficient-evidence",
        evidence_items=(),
    )

    assert result.outcome == "insufficient-evidence"
    assert result.evidence == ()


def test_subjective_claim_is_not_externally_verifiable() -> None:
    result = assessment(
        outcome="not-verifiable",
        classification="subjective",
        evidence_items=(),
    )

    assert result.claim.classification == "subjective"
    assert result.outcome == "not-verifiable"


@pytest.mark.parametrize(
    "outcome",
    [
        "supported",
        "contradicted",
        "outdated",
        "insufficient-evidence",
    ],
)
def test_subjective_claim_rejects_factual_verdicts(
    outcome: str,
) -> None:
    evidence_items = (
        ()
        if outcome == "insufficient-evidence"
        else (evidence(),)
    )

    with pytest.raises(
        VerificationValidationError,
        match="subjective",
    ):
        assessment(
            outcome=outcome,
            classification="subjective",
            evidence_items=evidence_items,
        )


def test_material_canonical_change_makes_assessment_stale() -> None:
    result = assessment()

    assert assessment_is_stale(
        result,
        current_canonical_revision="sha256:canonical-b",
        as_of=datetime(2026, 9, 25, 7, 0, tzinfo=UTC),
        max_age=timedelta(days=90),
    )


def test_old_verification_makes_assessment_stale() -> None:
    result = assessment(
        checked_at=datetime(
            2026,
            1,
            1,
            0,
            0,
            tzinfo=UTC,
        ),
    )

    assert assessment_is_stale(
        result,
        current_canonical_revision="sha256:canonical-a",
        as_of=datetime(2026, 9, 25, 7, 0, tzinfo=UTC),
        max_age=timedelta(days=90),
    )


def test_current_matching_assessment_is_not_stale() -> None:
    result = assessment()

    assert not assessment_is_stale(
        result,
        current_canonical_revision="sha256:canonical-a",
        as_of=datetime(2026, 9, 26, 6, 0, tzinfo=UTC),
        max_age=timedelta(days=90),
    )


@pytest.mark.parametrize(
    ("classification", "outcome"),
    [
        ("stable-factual", "supported"),
        ("time-sensitive", "outdated"),
        ("domain-specific", "insufficient-evidence"),
        ("subjective", "not-verifiable"),
    ],
)
def test_supported_claim_classifications_and_outcomes(
    classification: str,
    outcome: str,
) -> None:
    evidence_items = (
        ()
        if outcome in {
            "insufficient-evidence",
            "not-verifiable",
        }
        else (evidence(),)
    )

    result = assessment(
        classification=classification,
        outcome=outcome,
        evidence_items=evidence_items,
    )

    assert result.claim.classification == classification
    assert result.outcome == outcome


def test_timestamps_must_be_timezone_aware() -> None:
    with pytest.raises(
        VerificationValidationError,
        match="timezone-aware",
    ):
        EvidenceItem(
            source_id="source",
            source_uri="https://example.test/evidence",
            source_title="Evidence",
            retrieved_at=datetime(2026, 9, 25, 5, 0),
            excerpt="Evidence.",
        )


def test_staleness_policy_must_be_positive() -> None:
    with pytest.raises(
        VerificationValidationError,
        match="max_age",
    ):
        assessment_is_stale(
            assessment(),
            current_canonical_revision="sha256:canonical-a",
            as_of=datetime(2026, 9, 25, 7, 0, tzinfo=UTC),
            max_age=timedelta(0),
        )
