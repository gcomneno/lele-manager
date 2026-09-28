from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from lele_manager.application.factual_verification import (
    ClaimExtractionResult,
    EvidenceAssessmentResult,
    FactualVerificationService,
)
from lele_manager.application.lesson_writing import CanonicalLessonSnapshot
from lele_manager.core.factual_verification import (
    EvidenceItem,
    VerificationClaim,
)
from lele_manager.core.factual_verification_store import (
    FactualVerificationStore,
)


UTC = timezone.utc


def _snapshot() -> CanonicalLessonSnapshot:
    return CanonicalLessonSnapshot(
        lesson_id="python/releases",
        relative_path="python/releases.md",
        canonical_revision="sha256:canonical-a",
        text=(
            "Python 3.12 was released in October 2023. "
            "I prefer its error messages."
        ),
        topic="python",
        source="note",
        importance=3,
        tags=["python", "release"],
        date="2026-09-25",
        title="Python releases",
        reviewed_at=None,
        review_interval_days=None,
        lifecycle="active",
        superseded_by=None,
        relationships={},
    )


def _factual_claim() -> VerificationClaim:
    return VerificationClaim(
        claim_id="claim-release-date",
        text="Python 3.12 was released in October 2023.",
        classification="stable-factual",
    )


def _subjective_claim() -> VerificationClaim:
    return VerificationClaim(
        claim_id="claim-preference",
        text="Python 3.12 has better error messages.",
        classification="subjective",
    )


def _evidence() -> EvidenceItem:
    return EvidenceItem(
        source_id="python-3.12-release",
        source_uri="https://www.python.org/downloads/release/python-3120/",
        source_title="Python 3.12.0",
        retrieved_at=datetime(2026, 9, 25, 5, 0, tzinfo=UTC),
        excerpt="Python 3.12.0 was released on October 2, 2023.",
    )


class FakeExtractor:
    def __init__(self) -> None:
        self.inputs: list[tuple[str, str, str]] = []

    def extract(
        self,
        *,
        lesson_id: str,
        canonical_revision: str,
        text: str,
    ) -> ClaimExtractionResult:
        self.inputs.append(
            (lesson_id, canonical_revision, text)
        )
        return ClaimExtractionResult(
            claims=(
                _factual_claim(),
                _subjective_claim(),
            )
        )


class FakeRetriever:
    def __init__(self) -> None:
        self.claim_ids: list[str] = []

    def retrieve(
        self,
        *,
        claim: VerificationClaim,
    ) -> tuple[EvidenceItem, ...]:
        self.claim_ids.append(claim.claim_id)

        if claim.classification == "subjective":
            raise AssertionError(
                "subjective claims must not trigger evidence retrieval"
            )

        return (_evidence(),)


class FakeAssessor:
    def __init__(self) -> None:
        self.calls: list[
            tuple[str, tuple[EvidenceItem, ...]]
        ] = []

    def assess(
        self,
        *,
        claim: VerificationClaim,
        evidence: tuple[EvidenceItem, ...],
    ) -> EvidenceAssessmentResult:
        self.calls.append((claim.claim_id, evidence))

        return EvidenceAssessmentResult(
            outcome="supported",
            explanation=(
                "The primary Python release page supports "
                "the release-date claim."
            ),
        )


def test_service_uses_canonical_snapshot_and_persists_results(
    tmp_path: Path,
) -> None:
    extractor = FakeExtractor()
    retriever = FakeRetriever()
    assessor = FakeAssessor()
    store = FactualVerificationStore(
        tmp_path / "verification.json"
    )

    service = FactualVerificationService(
        extractor=extractor,
        retriever=retriever,
        assessor=assessor,
        store=store,
        now=lambda: datetime(
            2026,
            9,
            25,
            6,
            0,
            tzinfo=UTC,
        ),
    )

    result = service.verify(
        scope="vault-a",
        lesson=_snapshot(),
    )

    assert extractor.inputs == [
        (
            "python/releases",
            "sha256:canonical-a",
            _snapshot().text,
        )
    ]

    assert retriever.claim_ids == [
        "claim-release-date",
    ]

    assert assessor.calls == [
        (
            "claim-release-date",
            (_evidence(),),
        )
    ]

    assert [item.claim.claim_id for item in result] == [
        "claim-release-date",
        "claim-preference",
    ]

    assert result[0].outcome == "supported"
    assert result[0].evidence == (_evidence(),)
    assert result[0].canonical_revision == (
        "sha256:canonical-a"
    )

    assert result[1].outcome == "not-verifiable"
    assert result[1].evidence == ()
    assert result[1].claim.classification == "subjective"

    stored = store.list_assessments(
        scope="vault-a",
        lesson_id="python/releases",
    )

    assert [item.claim.claim_id for item in stored] == [
        "claim-preference",
        "claim-release-date",
    ]
    assert set(stored) == set(result)


def test_assessor_receives_only_retrieved_evidence(
    tmp_path: Path,
) -> None:
    assessor = FakeAssessor()

    service = FactualVerificationService(
        extractor=FakeExtractor(),
        retriever=FakeRetriever(),
        assessor=assessor,
        store=FactualVerificationStore(
            tmp_path / "verification.json"
        ),
        now=lambda: datetime(
            2026,
            9,
            25,
            6,
            0,
            tzinfo=UTC,
        ),
    )

    service.verify(
        scope="vault-a",
        lesson=_snapshot(),
    )

    assert assessor.calls == [
        (
            "claim-release-date",
            (_evidence(),),
        )
    ]


class EmptyRetriever:
    def retrieve(
        self,
        *,
        claim: VerificationClaim,
    ) -> tuple[EvidenceItem, ...]:
        return ()


class InsufficientAssessor:
    def assess(
        self,
        *,
        claim: VerificationClaim,
        evidence: tuple[EvidenceItem, ...],
    ) -> EvidenceAssessmentResult:
        assert evidence == ()

        return EvidenceAssessmentResult(
            outcome="insufficient-evidence",
            explanation="No maintained evidence was retrieved.",
        )


def test_empty_retrieval_can_produce_insufficient_evidence(
    tmp_path: Path,
) -> None:
    class OneClaimExtractor:
        def extract(
            self,
            *,
            lesson_id: str,
            canonical_revision: str,
            text: str,
        ) -> ClaimExtractionResult:
            return ClaimExtractionResult(
                claims=(_factual_claim(),)
            )

    service = FactualVerificationService(
        extractor=OneClaimExtractor(),
        retriever=EmptyRetriever(),
        assessor=InsufficientAssessor(),
        store=FactualVerificationStore(
            tmp_path / "verification.json"
        ),
        now=lambda: datetime(
            2026,
            9,
            25,
            6,
            0,
            tzinfo=UTC,
        ),
    )

    result = service.verify(
        scope="vault-a",
        lesson=_snapshot(),
    )

    assert len(result) == 1
    assert result[0].outcome == "insufficient-evidence"
    assert result[0].evidence == ()


def test_no_claims_produces_no_assessments(
    tmp_path: Path,
) -> None:
    class EmptyExtractor:
        def extract(
            self,
            *,
            lesson_id: str,
            canonical_revision: str,
            text: str,
        ) -> ClaimExtractionResult:
            return ClaimExtractionResult(claims=())

    class NeverRetriever:
        def retrieve(
            self,
            *,
            claim: VerificationClaim,
        ) -> tuple[EvidenceItem, ...]:
            raise AssertionError("must not retrieve")

    class NeverAssessor:
        def assess(
            self,
            *,
            claim: VerificationClaim,
            evidence: tuple[EvidenceItem, ...],
        ) -> EvidenceAssessmentResult:
            raise AssertionError("must not assess")

    store = FactualVerificationStore(
        tmp_path / "verification.json"
    )

    service = FactualVerificationService(
        extractor=EmptyExtractor(),
        retriever=NeverRetriever(),
        assessor=NeverAssessor(),
        store=store,
        now=lambda: datetime(
            2026,
            9,
            25,
            6,
            0,
            tzinfo=UTC,
        ),
    )

    assert service.verify(
        scope="vault-a",
        lesson=_snapshot(),
    ) == ()

    assert store.list_assessments(
        scope="vault-a",
        lesson_id="python/releases",
    ) == ()
