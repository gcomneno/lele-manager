from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

import pytest

from lele_manager.core.factual_verification import (
    EvidenceItem,
    VerificationAssessment,
    VerificationClaim,
)
from lele_manager.core.factual_verification_store import (
    FACTUAL_VERIFICATION_STORE_FILENAME,
    FactualVerificationStore,
    FactualVerificationStoreError,
    factual_verification_store_path,
)


UTC = timezone.utc


def _assessment(
    *,
    lesson_id: str = "python/releases",
    claim_id: str = "claim-1",
    canonical_revision: str = "sha256:canonical-a",
    outcome: str = "supported",
    checked_at: datetime | None = None,
) -> VerificationAssessment:
    evidence = (
        EvidenceItem(
            source_id="python-3.12-release",
            source_uri="https://www.python.org/downloads/release/python-3120/",
            source_title="Python 3.12.0",
            retrieved_at=datetime(2026, 9, 25, 5, 0, tzinfo=UTC),
            excerpt="Python 3.12.0 was released on October 2, 2023.",
        ),
    )

    return VerificationAssessment(
        lesson_id=lesson_id,
        canonical_revision=canonical_revision,
        claim=VerificationClaim(
            claim_id=claim_id,
            text="Python 3.12 was released in October 2023.",
            classification="stable-factual",
        ),
        outcome=outcome,
        evidence=evidence,
        checked_at=checked_at
        or datetime(2026, 9, 25, 6, 0, tzinfo=UTC),
        explanation="The primary release page supports the claim.",
    )


def test_default_path_uses_persistent_application_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path))

    assert (
        factual_verification_store_path()
        == tmp_path / FACTUAL_VERIFICATION_STORE_FILENAME
    )


def test_save_and_read_assessment_round_trip(tmp_path: Path) -> None:
    store = FactualVerificationStore(
        tmp_path / FACTUAL_VERIFICATION_STORE_FILENAME
    )
    expected = _assessment()

    stored = store.save_assessment(
        scope="vault-a",
        assessment=expected,
    )

    assert stored == expected
    assert store.list_assessments(
        scope="vault-a",
        lesson_id="python/releases",
    ) == (expected,)


def test_scope_and_lesson_filters_are_isolated(tmp_path: Path) -> None:
    store = FactualVerificationStore(tmp_path / "store.json")

    first = _assessment(
        lesson_id="python/releases",
        claim_id="claim-a",
    )
    second = _assessment(
        lesson_id="git/rebase",
        claim_id="claim-b",
    )

    store.save_assessment(scope="vault-a", assessment=first)
    store.save_assessment(scope="vault-a", assessment=second)
    store.save_assessment(scope="vault-b", assessment=first)

    assert store.list_assessments(
        scope="vault-a",
        lesson_id="python/releases",
    ) == (first,)
    assert store.list_assessments(
        scope="vault-a",
        lesson_id="git/rebase",
    ) == (second,)
    assert store.list_assessments(
        scope="vault-b",
        lesson_id="python/releases",
    ) == (first,)


def test_same_lesson_and_claim_replaces_previous_assessment(
    tmp_path: Path,
) -> None:
    path = tmp_path / "store.json"
    store = FactualVerificationStore(path)

    store.save_assessment(
        scope="vault-a",
        assessment=_assessment(
            canonical_revision="sha256:old",
            checked_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
    )
    latest = _assessment(
        canonical_revision="sha256:new",
        checked_at=datetime(2026, 9, 25, tzinfo=UTC),
    )
    store.save_assessment(
        scope="vault-a",
        assessment=latest,
    )

    assert store.list_assessments(
        scope="vault-a",
        lesson_id="python/releases",
    ) == (latest,)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["scopes"]["vault-a"]) == 1
    assert (
        data["scopes"]["vault-a"][0]["canonical_revision"]
        == "sha256:new"
    )


def test_multiple_claims_for_same_lesson_are_preserved_and_ordered(
    tmp_path: Path,
) -> None:
    store = FactualVerificationStore(tmp_path / "store.json")

    claim_b = _assessment(claim_id="claim-b")
    claim_a = _assessment(claim_id="claim-a")

    store.save_assessment(scope="vault-a", assessment=claim_b)
    store.save_assessment(scope="vault-a", assessment=claim_a)

    assert store.list_assessments(
        scope="vault-a",
        lesson_id="python/releases",
    ) == (
        claim_a,
        claim_b,
    )


@pytest.mark.parametrize(
    "payload",
    [
        "{not-json",
        json.dumps(
            {
                "schema_version": 999,
                "scopes": {},
            }
        ),
        json.dumps(
            {
                "schema_version": 1,
                "scopes": [],
            }
        ),
        json.dumps(
            {
                "schema_version": 1,
                "scopes": {
                    "vault-a": {},
                },
            }
        ),
        json.dumps(
            {
                "schema_version": 1,
                "scopes": {
                    "vault-a": [
                        {
                            "lesson_id": "python/releases",
                        }
                    ],
                },
            }
        ),
    ],
)
def test_malformed_store_payloads_fail_closed(
    tmp_path: Path,
    payload: str,
) -> None:
    path = tmp_path / "store.json"
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(FactualVerificationStoreError):
        FactualVerificationStore(path).list_assessments(
            scope="vault-a",
        )


def test_duplicate_lesson_claim_records_fail_closed(
    tmp_path: Path,
) -> None:
    path = tmp_path / "store.json"
    store = FactualVerificationStore(path)
    value = _assessment()

    store.save_assessment(
        scope="vault-a",
        assessment=value,
    )

    data = json.loads(path.read_text(encoding="utf-8"))
    data["scopes"]["vault-a"].append(
        dict(data["scopes"]["vault-a"][0])
    )
    path.write_text(
        json.dumps(data),
        encoding="utf-8",
    )

    with pytest.raises(
        FactualVerificationStoreError,
        match="duplicate",
    ):
        store.list_assessments(scope="vault-a")


def test_unsafe_symlink_and_non_regular_path_fail_closed(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")

    link = tmp_path / "link.json"
    link.symlink_to(target)

    with pytest.raises(FactualVerificationStoreError):
        FactualVerificationStore(link).list_assessments(
            scope="vault-a",
        )

    directory = tmp_path / "dir.json"
    directory.mkdir()

    with pytest.raises(FactualVerificationStoreError):
        FactualVerificationStore(directory).list_assessments(
            scope="vault-a",
        )


def test_oversize_store_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "store.json"
    path.write_bytes(
        b" " * (FactualVerificationStore.MAX_BYTES + 1)
    )

    with pytest.raises(
        FactualVerificationStoreError,
        match="size",
    ):
        FactualVerificationStore(path).list_assessments(
            scope="vault-a",
        )


def test_atomic_write_failure_preserves_previous_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "store.json"
    store = FactualVerificationStore(path)

    store.save_assessment(
        scope="vault-a",
        assessment=_assessment(),
    )
    before = path.read_bytes()

    def fail_replace(_src: str, _dst: Path) -> None:
        raise OSError("injected")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(FactualVerificationStoreError):
        store.save_assessment(
            scope="vault-a",
            assessment=_assessment(
                claim_id="claim-2",
            ),
        )

    assert path.read_bytes() == before


def test_read_only_lookup_does_not_rewrite_malformed_state(
    tmp_path: Path,
) -> None:
    path = tmp_path / "store.json"
    path.write_bytes(b"{not-json")
    before = path.read_bytes()

    with pytest.raises(FactualVerificationStoreError):
        FactualVerificationStore(path).list_assessments(
            scope="vault-a",
        )

    assert path.read_bytes() == before
