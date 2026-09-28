from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest

from lele_manager.application.factual_verification import (
    EvidenceAssessmentResult,
)
from lele_manager.core.factual_verification import (
    EvidenceItem,
    VerificationClaim,
)


def _response(
    handler,
) -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.openai.com",
    )


def test_claim_extractor_uses_sol_structured_output_without_web_search() -> None:
    from lele_manager.adapters.openai_factual_verification import (
        OpenAIClaimExtractor,
    )

    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["authorization"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)

        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {
                                        "claims": [
                                            {
                                                "claim_id": "claim-1",
                                                "text": (
                                                    "Python 3.12 was released "
                                                    "in October 2023."
                                                ),
                                                "classification": (
                                                    "stable-factual"
                                                ),
                                            }
                                        ]
                                    }
                                ),
                                "annotations": [],
                            }
                        ],
                    }
                ]
            },
        )

    with _response(handler) as client:
        extractor = OpenAIClaimExtractor(
            api_key="sk-user-secret",
            client=client,
        )

        result = extractor.extract(
            lesson_id="python/releases",
            canonical_revision="sha256:test",
            text="Python 3.12 was released in October 2023.",
        )

    assert len(result.claims) == 1
    assert result.claims[0].claim_id == "claim-1"
    assert result.claims[0].classification == "stable-factual"

    assert seen["path"] == "/v1/responses"
    assert seen["authorization"] == "Bearer sk-user-secret"

    body = seen["body"]
    assert isinstance(body, dict)
    assert body["model"] == "gpt-5.6"
    assert "tools" not in body
    assert body["reasoning"] == {"effort": "low"}

    text_format = body["text"]["format"]
    assert text_format["type"] == "json_schema"
    assert text_format["strict"] is True


def test_evidence_retriever_requires_live_web_search_and_preserves_sources() -> None:
    from lele_manager.adapters.openai_factual_verification import (
        OpenAIEvidenceRetriever,
    )

    seen: dict[str, object] = {}

    response_text = (
        "Python 3.12.0 was released on October 2, 2023. "
        "[Python release page]"
    )
    citation_start = response_text.index("[Python release page]")
    citation_end = len(response_text)

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)

        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "web_search_call",
                        "id": "ws_test",
                        "status": "completed",
                        "action": {
                            "type": "search",
                            "query": "Python 3.12 release date",
                        },
                    },
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": response_text,
                                "annotations": [
                                    {
                                        "type": "url_citation",
                                        "start_index": citation_start,
                                        "end_index": citation_end,
                                        "url": (
                                            "https://www.python.org/"
                                            "downloads/release/python-3120/"
                                        ),
                                        "title": "Python 3.12.0",
                                    }
                                ],
                            }
                        ],
                    },
                ]
            },
        )

    claim = VerificationClaim(
        claim_id="release-date",
        text="Python 3.12 was released in October 2023.",
        classification="stable-factual",
    )

    with _response(handler) as client:
        retriever = OpenAIEvidenceRetriever(
            api_key="sk-user-secret",
            client=client,
            now=lambda: datetime(
                2026,
                9,
                25,
                12,
                0,
                tzinfo=timezone.utc,
            ),
        )

        evidence = retriever.retrieve(claim=claim)

    assert len(evidence) == 1
    item = evidence[0]
    assert item.source_uri == (
        "https://www.python.org/downloads/release/python-3120/"
    )
    assert item.source_title == "Python 3.12.0"
    assert item.retrieved_at == datetime(
        2026,
        9,
        25,
        12,
        0,
        tzinfo=timezone.utc,
    )
    assert "Python 3.12.0 was released" in item.excerpt

    body = seen["body"]
    assert isinstance(body, dict)
    assert body["model"] == "gpt-5.6"
    assert body["reasoning"] == {"effort": "low"}
    assert body["tool_choice"] == "required"
    assert body["tools"] == [
        {
            "type": "web_search",
            "external_web_access": True,
        }
    ]


def test_evidence_retriever_returns_no_evidence_without_url_citations() -> None:
    from lele_manager.adapters.openai_factual_verification import (
        OpenAIEvidenceRetriever,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "web_search_call",
                        "id": "ws_test",
                        "status": "completed",
                        "action": {
                            "type": "search",
                            "query": "claim",
                        },
                    },
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "No authoritative source was found.",
                                "annotations": [],
                            }
                        ],
                    },
                ]
            },
        )

    claim = VerificationClaim(
        claim_id="claim-1",
        text="Some factual claim.",
        classification="stable-factual",
    )

    with _response(handler) as client:
        retriever = OpenAIEvidenceRetriever(
            api_key="sk-user-secret",
            client=client,
        )

        assert retriever.retrieve(claim=claim) == ()


def test_assessor_uses_only_supplied_evidence_and_no_web_tool() -> None:
    from lele_manager.adapters.openai_factual_verification import (
        OpenAIEvidenceAssessor,
    )

    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen["body"] = body

        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {
                                        "outcome": "supported",
                                        "explanation": (
                                            "The cited primary source "
                                            "supports the claim."
                                        ),
                                    }
                                ),
                                "annotations": [],
                            }
                        ],
                    }
                ]
            },
        )

    claim = VerificationClaim(
        claim_id="release-date",
        text="Python 3.12 was released in October 2023.",
        classification="stable-factual",
    )
    evidence = (
        EvidenceItem(
            source_id="source-1",
            source_uri=(
                "https://www.python.org/"
                "downloads/release/python-3120/"
            ),
            source_title="Python 3.12.0",
            retrieved_at=datetime(
                2026,
                9,
                25,
                12,
                0,
                tzinfo=timezone.utc,
            ),
            excerpt=(
                "Python 3.12.0 was released on October 2, 2023."
            ),
        ),
    )

    with _response(handler) as client:
        assessor = OpenAIEvidenceAssessor(
            api_key="sk-user-secret",
            client=client,
        )

        result = assessor.assess(
            claim=claim,
            evidence=evidence,
        )

    assert result == EvidenceAssessmentResult(
        outcome="supported",
        explanation="The cited primary source supports the claim.",
    )

    body = seen["body"]
    assert isinstance(body, dict)
    assert body["model"] == "gpt-5.6"
    assert body["reasoning"] == {"effort": "low"}
    assert "tools" not in body

    serialized = json.dumps(body)
    assert claim.text in serialized
    assert evidence[0].source_uri in serialized
    assert evidence[0].excerpt in serialized


def test_openai_http_failure_never_leaks_api_key() -> None:
    from lele_manager.adapters.openai_factual_verification import (
        OpenAIFactualVerificationError,
        OpenAIClaimExtractor,
    )

    secret = "sk-super-secret-user-key"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={
                "error": {
                    "message": f"invalid key {secret}",
                }
            },
        )

    with _response(handler) as client:
        extractor = OpenAIClaimExtractor(
            api_key=secret,
            client=client,
        )

        with pytest.raises(
            OpenAIFactualVerificationError,
        ) as exc_info:
            extractor.extract(
                lesson_id="test",
                canonical_revision="sha256:test",
                text="A factual statement.",
            )

    assert secret not in str(exc_info.value)
