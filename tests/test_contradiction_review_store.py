from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from lele_manager.core.contradiction_review_store import (
    CONTRADICTION_REVIEW_STORE_FILENAME,
    ContradictionReviewStore,
    ContradictionReviewStoreError,
    contradiction_review_decisions_path,
)


def test_default_path_uses_persistent_application_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LELE_DATA_DIR", str(tmp_path))
    assert contradiction_review_decisions_path() == tmp_path / CONTRADICTION_REVIEW_STORE_FILENAME


def test_different_context_and_dismissed_suppression_with_reversed_orientation(tmp_path: Path) -> None:
    store = ContradictionReviewStore(tmp_path / "contradiction-review-decisions.json")
    store.save_decision(
        scope="vault-a",
        left_id="b",
        left_fingerprint="fb",
        right_id="a",
        right_fingerprint="fa",
        decision="different-context",
    )
    assert store.is_suppressed(
        scope="vault-a", left_id="a", left_fingerprint="fa", right_id="b", right_fingerprint="fb"
    )
    store.save_decision(
        scope="vault-a",
        left_id="a",
        left_fingerprint="fa",
        right_id="c",
        right_fingerprint="fc",
        decision="dismissed",
    )
    assert store.is_suppressed(
        scope="vault-a", left_id="c", left_fingerprint="fc", right_id="a", right_fingerprint="fa"
    )


def test_changed_fingerprints_and_vault_isolation_invalidate_suppression(tmp_path: Path) -> None:
    store = ContradictionReviewStore(tmp_path / "store.json")
    store.save_decision(
        scope="vault-a",
        left_id="a",
        left_fingerprint="fa",
        right_id="b",
        right_fingerprint="fb",
        decision="dismissed",
    )
    assert not store.is_suppressed(
        scope="vault-a", left_id="a", left_fingerprint="changed", right_id="b", right_fingerprint="fb"
    )
    assert not store.is_suppressed(
        scope="vault-a", left_id="a", left_fingerprint="fa", right_id="b", right_fingerprint="changed"
    )
    assert not store.is_suppressed(
        scope="vault-b", left_id="a", left_fingerprint="fa", right_id="b", right_fingerprint="fb"
    )


def test_replacement_decision_for_same_pair(tmp_path: Path) -> None:
    path = tmp_path / "store.json"
    store = ContradictionReviewStore(path)
    store.save_decision(
        scope="vault-a",
        left_id="a",
        left_fingerprint="old-a",
        right_id="b",
        right_fingerprint="old-b",
        decision="dismissed",
    )
    store.save_decision(
        scope="vault-a",
        left_id="b",
        left_fingerprint="new-b",
        right_id="a",
        right_fingerprint="new-a",
        decision="different-context",
        note="separate source context",
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data["scopes"]["vault-a"]
    assert len(entries) == 1
    assert entries[0]["decision"] == "different-context"
    assert entries[0]["left_fingerprint"] == "new-a"
    assert entries[0]["right_fingerprint"] == "new-b"
    assert entries[0]["note"] == "separate source context"


@pytest.mark.parametrize(
    "payload",
    [
        "{not-json",
        json.dumps({"schema_version": 999, "generator_version": 1, "scopes": {}}),
        json.dumps({"schema_version": 1, "generator_version": 999, "scopes": {}}),
        json.dumps({"schema_version": 1, "generator_version": 1, "scopes": []}),
        json.dumps({"schema_version": 1, "generator_version": 1, "scopes": {"vault": {}}}),
        json.dumps(
            {
                "schema_version": 1,
                "generator_version": 1,
                "scopes": {
                    "vault": [
                        {
                            "left_id": "a",
                            "right_id": "b",
                            "left_fingerprint": "fa",
                            "right_fingerprint": "fb",
                            "decision": "unknown",
                            "decided_at": "2026-08-10T00:00:00+00:00",
                        }
                    ]
                },
            }
        ),
        json.dumps(
            {
                "schema_version": 1,
                "generator_version": 1,
                "scopes": {
                    "vault": [
                        {
                            "left_id": "a",
                            "right_id": "a",
                            "left_fingerprint": "fa",
                            "right_fingerprint": "fb",
                            "decision": "dismissed",
                            "decided_at": "2026-08-10T00:00:00+00:00",
                        }
                    ]
                },
            }
        ),
        json.dumps(
            {
                "schema_version": 1,
                "generator_version": 1,
                "scopes": {
                    "vault": [
                        {
                            "left_id": "b",
                            "right_id": "a",
                            "left_fingerprint": "fb",
                            "right_fingerprint": "fa",
                            "decision": "dismissed",
                            "decided_at": "2026-08-10T00:00:00+00:00",
                        }
                    ]
                },
            }
        ),
        json.dumps(
            {
                "schema_version": 1,
                "generator_version": 1,
                "scopes": {
                    "vault": [
                        {
                            "left_id": "a",
                            "right_id": "b",
                            "left_fingerprint": "",
                            "right_fingerprint": "fb",
                            "decision": "dismissed",
                            "decided_at": "2026-08-10T00:00:00+00:00",
                        }
                    ]
                },
            }
        ),
        json.dumps(
            {
                "schema_version": 1,
                "generator_version": 1,
                "scopes": {
                    "vault": [
                        {
                            "left_id": "a",
                            "right_id": "b",
                            "left_fingerprint": "fa",
                            "right_fingerprint": "fb",
                            "decision": "dismissed",
                            "decided_at": "not-a-timestamp",
                        }
                    ]
                },
            }
        ),
        json.dumps(
            {
                "schema_version": 1,
                "generator_version": 1,
                "scopes": {
                    "vault": [
                        {
                            "left_id": "a",
                            "right_id": "b",
                            "left_fingerprint": "fa",
                            "right_fingerprint": "fb",
                            "decision": "dismissed",
                            "decided_at": "2026-08-10T00:00:00+00:00",
                            "note": 5,
                        }
                    ]
                },
            }
        ),
    ],
)
def test_malformed_store_payloads_fail_closed(tmp_path: Path, payload: str) -> None:
    path = tmp_path / "store.json"
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(ContradictionReviewStoreError):
        ContradictionReviewStore(path).is_suppressed(
            scope="vault", left_id="a", left_fingerprint="fa", right_id="b", right_fingerprint="fb"
        )


def test_duplicate_pair_entries_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "store.json"
    entry = {
        "left_id": "a",
        "right_id": "b",
        "left_fingerprint": "fa",
        "right_fingerprint": "fb",
        "decision": "dismissed",
        "decided_at": "2026-08-10T00:00:00+00:00",
    }
    path.write_text(
        json.dumps({"schema_version": 1, "generator_version": 1, "scopes": {"vault": [entry, entry]}}),
        encoding="utf-8",
    )
    with pytest.raises(ContradictionReviewStoreError):
        ContradictionReviewStore(path).is_suppressed(
            scope="vault", left_id="a", left_fingerprint="fa", right_id="b", right_fingerprint="fb"
        )


def test_unsafe_symlink_and_non_regular_path_fail(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(ContradictionReviewStoreError):
        ContradictionReviewStore(link).is_suppressed(
            scope="vault", left_id="a", left_fingerprint="fa", right_id="b", right_fingerprint="fb"
        )
    directory = tmp_path / "dir.json"
    directory.mkdir()
    with pytest.raises(ContradictionReviewStoreError):
        ContradictionReviewStore(directory).is_suppressed(
            scope="vault", left_id="a", left_fingerprint="fa", right_id="b", right_fingerprint="fb"
        )


def test_oversize_file_fails(tmp_path: Path) -> None:
    path = tmp_path / "store.json"
    path.write_bytes(b" " * (ContradictionReviewStore.MAX_BYTES + 1))
    with pytest.raises(ContradictionReviewStoreError, match="size"):
        ContradictionReviewStore(path).is_suppressed(
            scope="vault", left_id="a", left_fingerprint="fa", right_id="b", right_fingerprint="fb"
        )


def test_atomic_write_failure_preserves_previous_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "store.json"
    store = ContradictionReviewStore(path)
    store.save_decision(
        scope="vault",
        left_id="a",
        left_fingerprint="fa",
        right_id="b",
        right_fingerprint="fb",
        decision="dismissed",
    )
    before = path.read_bytes()

    def fail_replace(_src: str, _dst: Path) -> None:
        raise OSError("injected")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(ContradictionReviewStoreError):
        store.save_decision(
            scope="vault",
            left_id="a",
            left_fingerprint="new-a",
            right_id="c",
            right_fingerprint="fc",
            decision="dismissed",
        )
    assert path.read_bytes() == before


def test_read_only_lookup_does_not_rewrite_malformed_state(tmp_path: Path) -> None:
    path = tmp_path / "store.json"
    path.write_bytes(b"{not-json")
    before = path.read_bytes()
    with pytest.raises(ContradictionReviewStoreError):
        ContradictionReviewStore(path).is_suppressed(
            scope="vault", left_id="a", left_fingerprint="fa", right_id="b", right_fingerprint="fb"
        )
    assert path.read_bytes() == before
