"""Persistent derived state for factual-verification assessments.

The store is scoped by Vault identity and contains advisory verification state
only. It is not canonical lesson knowledge and never mutates the Markdown
Vault.

Stored assessments are bound to the exact canonical revision that was checked.
A later canonical change does not rewrite or discard the record; callers can
use the factual-verification domain staleness contract to classify it as stale.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from lele_manager.core.factual_verification import (
    EvidenceItem,
    VerificationAssessment,
    VerificationClaim,
    VerificationValidationError,
)
from lele_manager.core.paths import data_dir


SCHEMA_VERSION = 1
FACTUAL_VERIFICATION_STORE_FILENAME = "factual-verification-results.json"

_STORE_LOCK = Lock()

_ASSESSMENT_FIELDS = {
    "lesson_id",
    "canonical_revision",
    "claim",
    "outcome",
    "evidence",
    "checked_at",
    "explanation",
}

_CLAIM_FIELDS = {
    "claim_id",
    "text",
    "classification",
}

_EVIDENCE_FIELDS = {
    "source_id",
    "source_uri",
    "source_title",
    "retrieved_at",
    "excerpt",
}


class FactualVerificationStoreError(Exception):
    """Persistent factual-verification state is invalid or unavailable."""


def factual_verification_store_path() -> Path:
    """Return the default persistent application-data path."""

    return data_dir() / FACTUAL_VERIFICATION_STORE_FILENAME


class FactualVerificationStore:
    """Fail-closed JSON store for current verification assessments."""

    MAX_BYTES = 32 * 1024 * 1024

    def __init__(self, path: Path) -> None:
        self.path = path

    def list_assessments(
        self,
        *,
        scope: str,
        lesson_id: str | None = None,
    ) -> tuple[VerificationAssessment, ...]:
        normalized_scope = _non_empty_string(scope, "scope")

        normalized_lesson_id: str | None = None
        if lesson_id is not None:
            normalized_lesson_id = _non_empty_string(
                lesson_id,
                "lesson_id",
            )

        with _STORE_LOCK:
            data = self._load()

        raw_entries = data["scopes"].get(normalized_scope, [])
        if not isinstance(raw_entries, list):
            raise FactualVerificationStoreError(
                "factual-verification scope is malformed"
            )

        assessments = tuple(
            _assessment_from_record(entry)
            for entry in raw_entries
            if normalized_lesson_id is None
            or (
                isinstance(entry, dict)
                and entry.get("lesson_id") == normalized_lesson_id
            )
        )

        return tuple(
            sorted(
                assessments,
                key=lambda item: (
                    item.lesson_id,
                    item.claim.claim_id,
                ),
            )
        )

    def save_assessment(
        self,
        *,
        scope: str,
        assessment: VerificationAssessment,
    ) -> VerificationAssessment:
        normalized_scope = _non_empty_string(scope, "scope")

        if type(assessment) is not VerificationAssessment:
            raise FactualVerificationStoreError(
                "assessment must be a VerificationAssessment"
            )

        record = _assessment_record(assessment)

        with _STORE_LOCK:
            data = self._load()

            raw_entries = data["scopes"].setdefault(
                normalized_scope,
                [],
            )
            if not isinstance(raw_entries, list):
                raise FactualVerificationStoreError(
                    "factual-verification scope is malformed"
                )

            raw_entries[:] = [
                entry
                for entry in raw_entries
                if not (
                    isinstance(entry, dict)
                    and entry.get("lesson_id") == assessment.lesson_id
                    and entry.get("claim", {}).get("claim_id")
                    == assessment.claim.claim_id
                )
            ]

            raw_entries.append(record)
            raw_entries.sort(key=_record_identity_sort_key)

            self._write(data)

        return assessment

    def _load(self) -> dict[str, Any]:
        try:
            node = self.path.lstat()
        except FileNotFoundError:
            return {
                "schema_version": SCHEMA_VERSION,
                "scopes": {},
            }
        except OSError as exc:
            raise FactualVerificationStoreError(
                "factual-verification state is unreadable"
            ) from exc

        if stat.S_ISLNK(node.st_mode) or not stat.S_ISREG(node.st_mode):
            raise FactualVerificationStoreError(
                "factual-verification state is unsafe"
            )

        if node.st_size > self.MAX_BYTES:
            raise FactualVerificationStoreError(
                "factual-verification state exceeds size limits"
            )

        try:
            data = json.loads(
                self.path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise FactualVerificationStoreError(
                "factual-verification state is unreadable"
            ) from exc

        _validate_store(data)
        return data

    def _write(self, data: dict[str, Any]) -> None:
        _validate_store(data)

        try:
            self.path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
        except OSError as exc:
            raise FactualVerificationStoreError(
                "factual-verification state could not be saved"
            ) from exc

        temp_name: str | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                delete=False,
            ) as handle:
                json.dump(
                    data,
                    handle,
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
                handle.write("\n")
                temp_name = handle.name

            os.replace(temp_name, self.path)
        except OSError as exc:
            if temp_name is not None:
                try:
                    Path(temp_name).unlink(missing_ok=True)
                except OSError:
                    pass

            raise FactualVerificationStoreError(
                "factual-verification state could not be saved"
            ) from exc


def _non_empty_string(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise FactualVerificationStoreError(
            f"factual-verification {name} is malformed"
        )
    return value.strip()


def _assessment_record(
    assessment: VerificationAssessment,
) -> dict[str, object]:
    return {
        "lesson_id": assessment.lesson_id,
        "canonical_revision": assessment.canonical_revision,
        "claim": {
            "claim_id": assessment.claim.claim_id,
            "text": assessment.claim.text,
            "classification": assessment.claim.classification,
        },
        "outcome": assessment.outcome,
        "evidence": [
            {
                "source_id": item.source_id,
                "source_uri": item.source_uri,
                "source_title": item.source_title,
                "retrieved_at": item.retrieved_at.isoformat(),
                "excerpt": item.excerpt,
            }
            for item in assessment.evidence
        ],
        "checked_at": assessment.checked_at.isoformat(),
        "explanation": assessment.explanation,
    }


def _assessment_from_record(
    value: object,
) -> VerificationAssessment:
    record = _validated_record(value)

    claim_record = record["claim"]
    evidence_records = record["evidence"]

    assert isinstance(claim_record, dict)
    assert isinstance(evidence_records, list)

    try:
        claim = VerificationClaim(
            claim_id=claim_record["claim_id"],
            text=claim_record["text"],
            classification=claim_record["classification"],
        )

        evidence = tuple(
            EvidenceItem(
                source_id=item["source_id"],
                source_uri=item["source_uri"],
                source_title=item["source_title"],
                retrieved_at=datetime.fromisoformat(
                    item["retrieved_at"]
                ),
                excerpt=item["excerpt"],
            )
            for item in evidence_records
        )

        return VerificationAssessment(
            lesson_id=record["lesson_id"],
            canonical_revision=record["canonical_revision"],
            claim=claim,
            outcome=record["outcome"],
            evidence=evidence,
            checked_at=datetime.fromisoformat(
                record["checked_at"]
            ),
            explanation=record["explanation"],
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        VerificationValidationError,
    ) as exc:
        raise FactualVerificationStoreError(
            "factual-verification entry is malformed"
        ) from exc


def _validate_store(value: object) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != {"schema_version", "scopes"}
        or value.get("schema_version") != SCHEMA_VERSION
        or not isinstance(value.get("scopes"), dict)
    ):
        raise FactualVerificationStoreError(
            "factual-verification state has an unsupported schema"
        )

    scopes = value["scopes"]
    assert isinstance(scopes, dict)

    for scope, entries in scopes.items():
        if (
            type(scope) is not str
            or not scope.strip()
            or not isinstance(entries, list)
        ):
            raise FactualVerificationStoreError(
                "factual-verification scope is malformed"
            )

        seen: set[tuple[str, str]] = set()

        for entry in entries:
            record = _validated_record(entry)

            claim = record["claim"]
            assert isinstance(claim, dict)

            identity = (
                record["lesson_id"],
                claim["claim_id"],
            )

            if identity in seen:
                raise FactualVerificationStoreError(
                    "factual-verification scope contains duplicate "
                    "lesson/claim records"
                )

            seen.add(identity)


def _validated_record(value: object) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != _ASSESSMENT_FIELDS
    ):
        raise FactualVerificationStoreError(
            "factual-verification entry is malformed"
        )

    scalar_fields = (
        "lesson_id",
        "canonical_revision",
        "outcome",
        "checked_at",
        "explanation",
    )

    if any(
        type(value.get(field)) is not str
        or not value[field].strip()
        for field in scalar_fields
    ):
        raise FactualVerificationStoreError(
            "factual-verification entry is malformed"
        )

    claim = value.get("claim")
    if (
        not isinstance(claim, dict)
        or set(claim) != _CLAIM_FIELDS
        or any(
            type(claim.get(field)) is not str
            or not claim[field].strip()
            for field in _CLAIM_FIELDS
        )
    ):
        raise FactualVerificationStoreError(
            "factual-verification claim is malformed"
        )

    evidence = value.get("evidence")
    if not isinstance(evidence, list):
        raise FactualVerificationStoreError(
            "factual-verification evidence is malformed"
        )

    for item in evidence:
        if (
            not isinstance(item, dict)
            or set(item) != _EVIDENCE_FIELDS
            or any(
                type(item.get(field)) is not str
                or not item[field].strip()
                for field in _EVIDENCE_FIELDS
            )
        ):
            raise FactualVerificationStoreError(
                "factual-verification evidence is malformed"
            )

    try:
        _assessment_from_validated_record(value)
    except (
        KeyError,
        TypeError,
        ValueError,
        VerificationValidationError,
    ) as exc:
        raise FactualVerificationStoreError(
            "factual-verification entry is malformed"
        ) from exc

    return value


def _assessment_from_validated_record(
    record: dict[str, Any],
) -> VerificationAssessment:
    claim_record = record["claim"]

    claim = VerificationClaim(
        claim_id=claim_record["claim_id"],
        text=claim_record["text"],
        classification=claim_record["classification"],
    )

    evidence = tuple(
        EvidenceItem(
            source_id=item["source_id"],
            source_uri=item["source_uri"],
            source_title=item["source_title"],
            retrieved_at=datetime.fromisoformat(
                item["retrieved_at"]
            ),
            excerpt=item["excerpt"],
        )
        for item in record["evidence"]
    )

    return VerificationAssessment(
        lesson_id=record["lesson_id"],
        canonical_revision=record["canonical_revision"],
        claim=claim,
        outcome=record["outcome"],
        evidence=evidence,
        checked_at=datetime.fromisoformat(
            record["checked_at"]
        ),
        explanation=record["explanation"],
    )


def _record_identity_sort_key(
    value: object,
) -> tuple[str, str]:
    if not isinstance(value, dict):
        return "", ""

    claim = value.get("claim")
    claim_id = (
        str(claim.get("claim_id"))
        if isinstance(claim, dict)
        else ""
    )

    return str(value.get("lesson_id", "")), claim_id
