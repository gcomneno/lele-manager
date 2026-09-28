"""Pure advisory domain contracts for evidence-backed factual verification.

This module owns no provider integration, network access, persistence, or
canonical mutation.

A verification assessment is derived review state tied to one exact canonical
lesson revision. Evidence-backed factual outcomes require explicit evidence;
model memory or an unexplained binary verdict is not evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, TypeAlias


ClaimClassification: TypeAlias = Literal[
    "stable-factual",
    "time-sensitive",
    "domain-specific",
    "subjective",
]

VerificationOutcome: TypeAlias = Literal[
    "supported",
    "contradicted",
    "outdated",
    "insufficient-evidence",
    "not-verifiable",
]

CLAIM_CLASSIFICATIONS: tuple[ClaimClassification, ...] = (
    "stable-factual",
    "time-sensitive",
    "domain-specific",
    "subjective",
)

VERIFICATION_OUTCOMES: tuple[VerificationOutcome, ...] = (
    "supported",
    "contradicted",
    "outdated",
    "insufficient-evidence",
    "not-verifiable",
)

_EVIDENCE_REQUIRED_OUTCOMES: frozenset[VerificationOutcome] = frozenset(
    {
        "supported",
        "contradicted",
        "outdated",
    }
)


class VerificationValidationError(ValueError):
    """Factual-verification state violates the maintained domain contract."""


def _non_empty_text(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise VerificationValidationError(f"{name} must be a non-empty string")
    if any("\ud800" <= character <= "\udfff" for character in value):
        raise VerificationValidationError(
            f"{name} must not contain Unicode surrogate code points"
        )
    return value.strip()


def _aware_datetime(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise VerificationValidationError(f"{name} must be a datetime")
    offset = value.utcoffset()
    if value.tzinfo is None or offset is None:
        raise VerificationValidationError(
            f"{name} must be timezone-aware"
        )
    return value


@dataclass(frozen=True, slots=True)
class VerificationClaim:
    """One bounded claim extracted from canonical lesson knowledge."""

    claim_id: str
    text: str
    classification: ClaimClassification

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "claim_id",
            _non_empty_text(self.claim_id, "claim_id"),
        )
        object.__setattr__(
            self,
            "text",
            _non_empty_text(self.text, "claim text"),
        )

        if self.classification not in CLAIM_CLASSIFICATIONS:
            raise VerificationValidationError(
                "classification must be one of: "
                + ", ".join(CLAIM_CLASSIFICATIONS)
            )


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """One explicit external evidence item used during assessment."""

    source_id: str
    source_uri: str
    source_title: str
    retrieved_at: datetime
    excerpt: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_id",
            _non_empty_text(self.source_id, "source_id"),
        )
        object.__setattr__(
            self,
            "source_uri",
            _non_empty_text(self.source_uri, "source_uri"),
        )
        object.__setattr__(
            self,
            "source_title",
            _non_empty_text(self.source_title, "source_title"),
        )
        object.__setattr__(
            self,
            "excerpt",
            _non_empty_text(self.excerpt, "evidence excerpt"),
        )
        _aware_datetime(self.retrieved_at, "retrieved_at")


@dataclass(frozen=True, slots=True)
class VerificationAssessment:
    """Evidence-backed advisory assessment for one exact canonical revision."""

    lesson_id: str
    canonical_revision: str
    claim: VerificationClaim
    outcome: VerificationOutcome
    evidence: tuple[EvidenceItem, ...]
    checked_at: datetime
    explanation: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "lesson_id",
            _non_empty_text(self.lesson_id, "lesson_id"),
        )
        object.__setattr__(
            self,
            "canonical_revision",
            _non_empty_text(
                self.canonical_revision,
                "canonical_revision",
            ),
        )

        if type(self.claim) is not VerificationClaim:
            raise VerificationValidationError(
                "claim must be a VerificationClaim"
            )

        if self.outcome not in VERIFICATION_OUTCOMES:
            raise VerificationValidationError(
                "outcome must be one of: "
                + ", ".join(VERIFICATION_OUTCOMES)
            )

        if type(self.evidence) is not tuple:
            raise VerificationValidationError(
                "evidence must be a tuple"
            )
        if not all(type(item) is EvidenceItem for item in self.evidence):
            raise VerificationValidationError(
                "evidence must contain EvidenceItem values"
            )

        if self.outcome in _EVIDENCE_REQUIRED_OUTCOMES and not self.evidence:
            raise VerificationValidationError(
                f"{self.outcome} outcome requires evidence"
            )

        if self.claim.classification == "subjective":
            if self.outcome != "not-verifiable":
                raise VerificationValidationError(
                    "subjective claims require a not-verifiable outcome"
                )

        _aware_datetime(self.checked_at, "checked_at")
        object.__setattr__(
            self,
            "explanation",
            _non_empty_text(self.explanation, "explanation"),
        )


def assessment_is_stale(
    assessment: VerificationAssessment,
    *,
    current_canonical_revision: str,
    as_of: datetime,
    max_age: timedelta,
) -> bool:
    """Return whether a verification assessment is no longer current.

    Staleness is derived and advisory. It is true when either:

    - the current canonical lesson revision differs from the verified revision;
    - the assessment age has reached or exceeded the configured maximum age.

    No canonical state is mutated.
    """

    if type(assessment) is not VerificationAssessment:
        raise VerificationValidationError(
            "assessment must be a VerificationAssessment"
        )

    current_revision = _non_empty_text(
        current_canonical_revision,
        "current_canonical_revision",
    )
    checked_at = _aware_datetime(
        assessment.checked_at,
        "checked_at",
    )
    current_time = _aware_datetime(as_of, "as_of")

    if not isinstance(max_age, timedelta) or max_age <= timedelta(0):
        raise VerificationValidationError(
            "max_age must be a positive timedelta"
        )

    if current_revision != assessment.canonical_revision:
        return True

    age = current_time - checked_at
    if age < timedelta(0):
        age = timedelta(0)

    return age >= max_age
