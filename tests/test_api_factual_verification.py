from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from lele_manager.api import server
from lele_manager.application.factual_verification import (
    ClaimExtractionResult,
    EvidenceAssessmentResult,
    FactualVerificationService,
)
from lele_manager.core.factual_verification import (
    EvidenceItem,
    VerificationClaim,
)
from lele_manager.core.factual_verification_store import (
    FACTUAL_VERIFICATION_STORE_FILENAME,
    FactualVerificationStore,
)
from lele_manager.core.vault import write_lesson_markdown


UTC = timezone.utc


def _write_lesson(
    vault: Path,
    *,
    body: str,
) -> None:
    write_lesson_markdown(
        vault,
        lesson_id="python/releases",
        body=body,
        topic="python",
        source="private-test-source",
        importance=3,
        tags=["python", "release"],
        date="2026-09-25",
        title="Python releases",
    )


class FakeExtractor:
    def extract(
        self,
        *,
        lesson_id: str,
        canonical_revision: str,
        text: str,
    ) -> ClaimExtractionResult:
        assert lesson_id == "python/releases"
        assert canonical_revision
        assert "Python 3.12" in text

        return ClaimExtractionResult(
            claims=(
                VerificationClaim(
                    claim_id="release-date",
                    text=(
                        "Python 3.12 was released "
                        "in October 2023."
                    ),
                    classification="stable-factual",
                ),
                VerificationClaim(
                    claim_id="preference",
                    text="Python 3.12 feels nicer.",
                    classification="subjective",
                ),
            )
        )


class FakeRetriever:
    def retrieve(
        self,
        *,
        claim: VerificationClaim,
    ) -> tuple[EvidenceItem, ...]:
        assert claim.claim_id == "release-date"

        return (
            EvidenceItem(
                source_id="python-3.12-release",
                source_uri=(
                    "https://www.python.org/downloads/"
                    "release/python-3120/"
                ),
                source_title="Python 3.12.0",
                retrieved_at=datetime.now(UTC),
                excerpt=(
                    "Python 3.12.0 was released "
                    "on October 2, 2023."
                ),
            ),
        )


class FakeAssessor:
    def assess(
        self,
        *,
        claim: VerificationClaim,
        evidence: tuple[EvidenceItem, ...],
    ) -> EvidenceAssessmentResult:
        assert claim.claim_id == "release-date"
        assert evidence

        return EvidenceAssessmentResult(
            outcome="supported",
            explanation=(
                "The primary release page supports "
                "the release-date claim."
            ),
        )


def _service(
    context,
) -> FactualVerificationService:
    return FactualVerificationService(
        extractor=FakeExtractor(),
        retriever=FakeRetriever(),
        assessor=FakeAssessor(),
        store=FactualVerificationStore(
            context.candidates_path.parent
            / FACTUAL_VERIFICATION_STORE_FILENAME
        ),
        now=lambda: datetime.now(UTC),
    )


def test_post_requires_explicit_remote_processing_approval(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "LELE_DATA_DIR",
        str(tmp_path / "data"),
    )
    context = server.get_active_vault_context()
    _write_lesson(
        context.vault_dir,
        body=(
            "Python 3.12 was released in October 2023. "
            "Python 3.12 feels nicer."
        ),
    )

    invoked = False

    def forbidden_service(_context):
        nonlocal invoked
        invoked = True
        raise AssertionError(
            "verification service must not run without consent"
        )

    monkeypatch.setattr(
        server,
        "_factual_verification_service",
        forbidden_service,
    )

    response = TestClient(server.app).post(
        "/lessons/python/releases/factual-verification",
        json={
            "remote_processing_approved": False,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == (
        "factual_verification_remote_consent_required"
    )
    assert invoked is False


def test_post_verifies_current_canonical_lesson_and_persists_review_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "LELE_DATA_DIR",
        str(tmp_path / "data"),
    )
    context = server.get_active_vault_context()
    _write_lesson(
        context.vault_dir,
        body=(
            "Python 3.12 was released in October 2023. "
            "Python 3.12 feels nicer."
        ),
    )

    monkeypatch.setattr(
        server,
        "_factual_verification_service",
        _service,
    )

    client = TestClient(server.app)

    response = client.post(
        "/lessons/python/releases/factual-verification",
        json={
            "remote_processing_approved": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["lesson_id"] == "python/releases"
    assert payload["remote_processing_approved"] is True
    assert len(payload["assessments"]) == 2

    by_claim = {
        item["claim"]["claim_id"]: item
        for item in payload["assessments"]
    }

    assert by_claim["release-date"]["outcome"] == "supported"
    assert (
        by_claim["release-date"]["evidence"][0]["source_id"]
        == "python-3.12-release"
    )
    assert (
        by_claim["preference"]["outcome"]
        == "not-verifiable"
    )
    assert by_claim["preference"]["evidence"] == []

    stored = client.get(
        "/lessons/python/releases/factual-verification"
    )

    assert stored.status_code == 200
    stored_payload = stored.json()

    assert stored_payload["lesson_id"] == "python/releases"
    assert len(stored_payload["assessments"]) == 2
    assert all(
        item["stale"] is False
        for item in stored_payload["assessments"]
    )


def test_get_marks_saved_verification_stale_after_canonical_change(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "LELE_DATA_DIR",
        str(tmp_path / "data"),
    )
    context = server.get_active_vault_context()

    _write_lesson(
        context.vault_dir,
        body="Python 3.12 was released in October 2023.",
    )

    monkeypatch.setattr(
        server,
        "_factual_verification_service",
        _service,
    )

    client = TestClient(server.app)

    verified = client.post(
        "/lessons/python/releases/factual-verification",
        json={
            "remote_processing_approved": True,
        },
    )
    assert verified.status_code == 200

    _write_lesson(
        context.vault_dir,
        body=(
            "Python 3.12 was released in October 2023. "
            "Canonical material changed after verification."
        ),
    )

    response = client.get(
        "/lessons/python/releases/factual-verification"
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["assessments"]
    assert all(
        item["stale"] is True
        for item in payload["assessments"]
    )


def test_verification_requires_existing_unambiguous_canonical_lesson(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "LELE_DATA_DIR",
        str(tmp_path / "data"),
    )

    monkeypatch.setattr(
        server,
        "_factual_verification_service",
        _service,
    )

    response = TestClient(server.app).post(
        "/lessons/python/missing/factual-verification",
        json={
            "remote_processing_approved": True,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == (
        "factual_verification_lesson_not_found"
    )
