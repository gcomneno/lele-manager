"""OpenAI adapter for evidence-backed factual verification.

The adapter keeps three responsibilities separate:

- claim extraction: structured inference, no web access;
- evidence retrieval: explicit OpenAI web search with attributable sources;
- evidence assessment: structured inference over supplied evidence only.

Model memory is never accepted as factual evidence.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Final, cast

import httpx

from lele_manager.application.factual_verification import (
    ClaimExtractionResult,
    EvidenceAssessmentResult,
)
from lele_manager.core.factual_verification import (
    EvidenceItem,
    VerificationClaim,
    VerificationOutcome,
)


_OPENAI_RESPONSES_PATH: Final = "/v1/responses"
_DEFAULT_MODEL: Final = "gpt-5.6"


_CLAIM_SCHEMA: Final[dict[str, object]] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["claims"],
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "claim_id",
                    "text",
                    "classification",
                ],
                "properties": {
                    "claim_id": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "text": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "classification": {
                        "type": "string",
                        "enum": [
                            "stable-factual",
                            "time-sensitive",
                            "domain-specific",
                            "subjective",
                        ],
                    },
                },
            },
        },
    },
}


_ASSESSMENT_SCHEMA: Final[dict[str, object]] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["outcome", "explanation"],
    "properties": {
        "outcome": {
            "type": "string",
            "enum": [
                "supported",
                "contradicted",
                "outdated",
                "insufficient-evidence",
                "not-verifiable",
            ],
        },
        "explanation": {
            "type": "string",
            "minLength": 1,
        },
    },
}


class OpenAIFactualVerificationError(RuntimeError):
    """Sanitized OpenAI factual-verification adapter failure."""


def _default_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_client() -> httpx.Client:
    return httpx.Client(
        base_url="https://api.openai.com",
        timeout=30.0,
    )


class _OpenAIAdapterBase:
    def __init__(
        self,
        *,
        api_key: str,
        client: httpx.Client | None = None,
        model: str = _DEFAULT_MODEL,
    ) -> None:
        key = api_key.strip()
        if not key:
            raise ValueError("api_key must be non-empty")

        selected_model = model.strip()
        if not selected_model:
            raise ValueError("model must be non-empty")

        self._api_key = key
        self._client = client if client is not None else _new_client()
        self._model = selected_model

    def _post(self, body: Mapping[str, object]) -> Mapping[str, object]:
        try:
            response = self._client.post(
                _OPENAI_RESPONSES_PATH,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=dict(body),
            )
            response.raise_for_status()
            payload = response.json()
        except (
            httpx.HTTPError,
            json.JSONDecodeError,
            ValueError,
        ) as exc:
            raise OpenAIFactualVerificationError(
                "OpenAI factual-verification request failed"
            ) from exc

        if not isinstance(payload, Mapping):
            raise OpenAIFactualVerificationError(
                "OpenAI factual-verification response is invalid"
            )

        return cast(Mapping[str, object], payload)

    @staticmethod
    def _output_text(
        payload: Mapping[str, object],
    ) -> tuple[str, tuple[Mapping[str, object], ...]]:
        output = payload.get("output")
        if not isinstance(output, list):
            raise OpenAIFactualVerificationError(
                "OpenAI response is missing output"
            )

        for item in output:
            if not isinstance(item, Mapping):
                continue
            if item.get("type") != "message":
                continue

            content = item.get("content")
            if not isinstance(content, list):
                continue

            for part in content:
                if not isinstance(part, Mapping):
                    continue
                if part.get("type") != "output_text":
                    continue

                text = part.get("text")
                if not isinstance(text, str) or not text.strip():
                    raise OpenAIFactualVerificationError(
                        "OpenAI response contains invalid output text"
                    )

                raw_annotations = part.get("annotations", [])
                if not isinstance(raw_annotations, list):
                    raise OpenAIFactualVerificationError(
                        "OpenAI response contains invalid annotations"
                    )

                annotations: list[Mapping[str, object]] = []
                for annotation in raw_annotations:
                    if isinstance(annotation, Mapping):
                        annotations.append(
                            cast(Mapping[str, object], annotation)
                        )

                return text, tuple(annotations)

        raise OpenAIFactualVerificationError(
            "OpenAI response contains no output text"
        )

    @classmethod
    def _structured_output(
        cls,
        payload: Mapping[str, object],
    ) -> Mapping[str, object]:
        text, _ = cls._output_text(payload)

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise OpenAIFactualVerificationError(
                "OpenAI structured response is invalid"
            ) from exc

        if not isinstance(parsed, Mapping):
            raise OpenAIFactualVerificationError(
                "OpenAI structured response is invalid"
            )

        return cast(Mapping[str, object], parsed)


class OpenAIClaimExtractor(_OpenAIAdapterBase):
    """Extract bounded atomic claims without performing web searches."""

    def extract(
        self,
        *,
        lesson_id: str,
        canonical_revision: str,
        text: str,
    ) -> ClaimExtractionResult:
        payload = self._post(
            {
                "model": self._model,
                "reasoning": {"effort": "low"},
                "instructions": (
                    "Extract atomic claims from the supplied Lesson Learned. "
                    "Classify each as stable-factual, time-sensitive, "
                    "domain-specific, or subjective. "
                    "Do not verify claims and do not use model memory as "
                    "evidence. Preserve only the minimum text needed for each "
                    "claim."
                ),
                "input": json.dumps(
                    {
                        "lesson_id": lesson_id,
                        "canonical_revision": canonical_revision,
                        "text": text,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "factual_verification_claims",
                        "strict": True,
                        "schema": _CLAIM_SCHEMA,
                    }
                },
            }
        )

        raw = self._structured_output(payload)
        raw_claims = raw.get("claims")

        if not isinstance(raw_claims, list):
            raise OpenAIFactualVerificationError(
                "OpenAI claim extraction result is invalid"
            )

        claims: list[VerificationClaim] = []

        for raw_claim in raw_claims:
            if not isinstance(raw_claim, Mapping):
                raise OpenAIFactualVerificationError(
                    "OpenAI claim extraction result is invalid"
                )

            if set(raw_claim) != {
                "claim_id",
                "text",
                "classification",
            }:
                raise OpenAIFactualVerificationError(
                    "OpenAI claim extraction result is invalid"
                )

            claim_id = raw_claim["claim_id"]
            claim_text = raw_claim["text"]
            classification = raw_claim["classification"]

            if (
                not isinstance(claim_id, str)
                or not isinstance(claim_text, str)
                or classification
                not in {
                    "stable-factual",
                    "time-sensitive",
                    "domain-specific",
                    "subjective",
                }
            ):
                raise OpenAIFactualVerificationError(
                    "OpenAI claim extraction result is invalid"
                )

            try:
                claims.append(
                    VerificationClaim(
                        claim_id=claim_id,
                        text=claim_text,
                        classification=classification,
                    )
                )
            except (TypeError, ValueError) as exc:
                raise OpenAIFactualVerificationError(
                    "OpenAI claim extraction result is invalid"
                ) from exc

        try:
            return ClaimExtractionResult(tuple(claims))
        except (TypeError, ValueError) as exc:
            raise OpenAIFactualVerificationError(
                "OpenAI claim extraction result is invalid"
            ) from exc


class OpenAIEvidenceRetriever(_OpenAIAdapterBase):
    """Retrieve attributable external evidence through explicit web search."""

    def __init__(
        self,
        *,
        api_key: str,
        client: httpx.Client | None = None,
        model: str = _DEFAULT_MODEL,
        now: Callable[[], datetime] = _default_now,
    ) -> None:
        super().__init__(
            api_key=api_key,
            client=client,
            model=model,
        )
        self._now = now

    def retrieve(
        self,
        *,
        claim: VerificationClaim,
    ) -> tuple[EvidenceItem, ...]:
        payload = self._post(
            {
                "model": self._model,
                "reasoning": {"effort": "low"},
                "instructions": (
                    "Find authoritative evidence relevant to the supplied "
                    "claim. Prefer primary and official sources. "
                    "Use live web search. Do not decide whether the claim is "
                    "true or false. Summarize only evidence supported by "
                    "cited web sources."
                ),
                "input": json.dumps(
                    {
                        "claim_id": claim.claim_id,
                        "claim": claim.text,
                        "classification": claim.classification,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "tools": [
                    {
                        "type": "web_search",
                        "external_web_access": True,
                    }
                ],
                "tool_choice": "required",
            }
        )

        text, annotations = self._output_text(payload)
        retrieved_at = self._now()

        evidence: list[EvidenceItem] = []
        seen_urls: set[str] = set()

        for annotation in annotations:
            if annotation.get("type") != "url_citation":
                continue

            url = annotation.get("url")
            title = annotation.get("title")

            if (
                not isinstance(url, str)
                or not url.strip()
                or not isinstance(title, str)
                or not title.strip()
                or url in seen_urls
            ):
                continue

            seen_urls.add(url)

            source_id = hashlib.sha256(
                url.encode("utf-8")
            ).hexdigest()

            try:
                evidence.append(
                    EvidenceItem(
                        source_id=source_id,
                        source_uri=url,
                        source_title=title,
                        retrieved_at=retrieved_at,
                        excerpt=text,
                    )
                )
            except (TypeError, ValueError) as exc:
                raise OpenAIFactualVerificationError(
                    "OpenAI web-search evidence is invalid"
                ) from exc

        return tuple(evidence)


class OpenAIEvidenceAssessor(_OpenAIAdapterBase):
    """Assess a claim strictly from the evidence supplied by the caller."""

    def assess(
        self,
        *,
        claim: VerificationClaim,
        evidence: tuple[EvidenceItem, ...],
    ) -> EvidenceAssessmentResult:
        payload = self._post(
            {
                "model": self._model,
                "reasoning": {"effort": "low"},
                "instructions": (
                    "Assess the claim using only the supplied evidence. "
                    "Do not use outside knowledge or model memory. "
                    "Return supported, contradicted, outdated, "
                    "insufficient-evidence, or not-verifiable. "
                    "Supported, contradicted, and outdated require direct "
                    "support from the supplied evidence."
                ),
                "input": json.dumps(
                    {
                        "claim": {
                            "claim_id": claim.claim_id,
                            "text": claim.text,
                            "classification": claim.classification,
                        },
                        "evidence": [
                            {
                                "source_id": item.source_id,
                                "source_uri": item.source_uri,
                                "source_title": item.source_title,
                                "retrieved_at": (
                                    item.retrieved_at.isoformat()
                                ),
                                "excerpt": item.excerpt,
                            }
                            for item in evidence
                        ],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "factual_verification_assessment",
                        "strict": True,
                        "schema": _ASSESSMENT_SCHEMA,
                    }
                },
            }
        )

        raw = self._structured_output(payload)

        if set(raw) != {"outcome", "explanation"}:
            raise OpenAIFactualVerificationError(
                "OpenAI assessment result is invalid"
            )

        outcome = raw["outcome"]
        explanation = raw["explanation"]

        valid_outcomes = {
            "supported",
            "contradicted",
            "outdated",
            "insufficient-evidence",
            "not-verifiable",
        }

        if (
            not isinstance(outcome, str)
            or outcome not in valid_outcomes
            or not isinstance(explanation, str)
            or not explanation.strip()
        ):
            raise OpenAIFactualVerificationError(
                "OpenAI assessment result is invalid"
            )

        return EvidenceAssessmentResult(
            outcome=cast(VerificationOutcome, outcome),
            explanation=explanation,
        )
