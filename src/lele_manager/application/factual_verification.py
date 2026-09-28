"""Application orchestration for evidence-backed factual verification.

This module owns workflow composition only:

canonical snapshot
    -> claim extraction
    -> bounded evidence retrieval
    -> evidence assessment
    -> derived verification persistence

Provider integration and network behavior live behind consumer-owned ports.
The service never mutates canonical Markdown.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from lele_manager.application.lesson_writing import CanonicalLessonSnapshot
from lele_manager.core.factual_verification import (
    EvidenceItem,
    VerificationAssessment,
    VerificationClaim,
    VerificationOutcome,
    VerificationValidationError,
)
from lele_manager.core.factual_verification_store import (
    FactualVerificationStore,
)


@dataclass(frozen=True, slots=True)
class ClaimExtractionResult:
    """Validated claims extracted from one exact canonical lesson revision."""

    claims: tuple[VerificationClaim, ...]

    def __post_init__(self) -> None:
        if type(self.claims) is not tuple:
            raise VerificationValidationError(
                "extracted claims must be a tuple"
            )

        if not all(
            type(claim) is VerificationClaim
            for claim in self.claims
        ):
            raise VerificationValidationError(
                "extracted claims must contain VerificationClaim values"
            )

        claim_ids = tuple(claim.claim_id for claim in self.claims)
        if len(claim_ids) != len(set(claim_ids)):
            raise VerificationValidationError(
                "extracted claim IDs must be unique"
            )


@dataclass(frozen=True, slots=True)
class EvidenceAssessmentResult:
    """Advisory outcome returned after assessing retrieved evidence."""

    outcome: VerificationOutcome
    explanation: str

    def __post_init__(self) -> None:
        if not isinstance(self.explanation, str) or not self.explanation.strip():
            raise VerificationValidationError(
                "assessment explanation must be a non-empty string"
            )


class ClaimExtractor(Protocol):
    """Extract bounded claims from one exact canonical lesson."""

    def extract(
        self,
        *,
        lesson_id: str,
        canonical_revision: str,
        text: str,
    ) -> ClaimExtractionResult: ...


class EvidenceRetriever(Protocol):
    """Retrieve external evidence for one bounded claim."""

    def retrieve(
        self,
        *,
        claim: VerificationClaim,
    ) -> tuple[EvidenceItem, ...]: ...


class EvidenceAssessor(Protocol):
    """Assess one claim using only the supplied retrieved evidence."""

    def assess(
        self,
        *,
        claim: VerificationClaim,
        evidence: tuple[EvidenceItem, ...],
    ) -> EvidenceAssessmentResult: ...


class FactualVerificationService:
    """Orchestrate advisory verification for one canonical lesson snapshot."""

    def __init__(
        self,
        *,
        extractor: ClaimExtractor,
        retriever: EvidenceRetriever,
        assessor: EvidenceAssessor,
        store: FactualVerificationStore,
        now: Callable[[], datetime],
    ) -> None:
        self._extractor = extractor
        self._retriever = retriever
        self._assessor = assessor
        self._store = store
        self._now = now

    def verify(
        self,
        *,
        scope: str,
        lesson: CanonicalLessonSnapshot,
    ) -> tuple[VerificationAssessment, ...]:
        if type(lesson) is not CanonicalLessonSnapshot:
            raise VerificationValidationError(
                "lesson must be a CanonicalLessonSnapshot"
            )

        extracted = self._extractor.extract(
            lesson_id=lesson.lesson_id,
            canonical_revision=lesson.canonical_revision,
            text=lesson.text,
        )

        if type(extracted) is not ClaimExtractionResult:
            raise VerificationValidationError(
                "claim extractor returned an invalid result"
            )

        assessments: list[VerificationAssessment] = []

        for claim in extracted.claims:
            if claim.classification == "subjective":
                assessment = VerificationAssessment(
                    lesson_id=lesson.lesson_id,
                    canonical_revision=lesson.canonical_revision,
                    claim=claim,
                    outcome="not-verifiable",
                    evidence=(),
                    checked_at=self._now(),
                    explanation=(
                        "The claim is subjective and is not suitable "
                        "for external factual verification."
                    ),
                )
            else:
                evidence = self._retriever.retrieve(
                    claim=claim,
                )

                if type(evidence) is not tuple or not all(
                    type(item) is EvidenceItem
                    for item in evidence
                ):
                    raise VerificationValidationError(
                        "evidence retriever returned invalid evidence"
                    )

                assessed = self._assessor.assess(
                    claim=claim,
                    evidence=evidence,
                )

                if type(assessed) is not EvidenceAssessmentResult:
                    raise VerificationValidationError(
                        "evidence assessor returned an invalid result"
                    )

                assessment = VerificationAssessment(
                    lesson_id=lesson.lesson_id,
                    canonical_revision=lesson.canonical_revision,
                    claim=claim,
                    outcome=assessed.outcome,
                    evidence=evidence,
                    checked_at=self._now(),
                    explanation=assessed.explanation,
                )

            self._store.save_assessment(
                scope=scope,
                assessment=assessment,
            )
            assessments.append(assessment)

        return tuple(assessments)
